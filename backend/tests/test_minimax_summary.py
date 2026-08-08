import unittest
from unittest.mock import Mock, patch

from app.services.content_analysis import TranscriptSegment
from app.integrations.minimax import (
    OrganizedChapter,
    OrganizedSubtitleCorrection,
    OrganizedTermCorrection,
    OrganizedVideo,
    apply_organization_corrections,
    extract_json,
    request_organization,
)


class MinimaxSummaryTests(unittest.TestCase):
    def test_extracts_json_after_reasoning_block(self) -> None:
        content = (
            "<think>internal reasoning</think>\n"
            "```json\n"
            '{"short_description":"这是足够长的一句话视频简介",'
            '"summary":"这是一段足够具体且长度满足要求的视频内容摘要，用于验证结构化输出。",'
            '"tags":["人工智能","产品设计","演示"],'
            '"chapters":[{"title":"产品配置与模型切换","start_seconds":0,'
            '"end_seconds":60,"summary":"演示如何配置模型并切换不同的 AI 服务。"}]}\n'
            "```"
        )
        value = extract_json(content)
        self.assertEqual(value["chapters"][0]["title"], "产品配置与模型切换")

    def test_rejects_non_json_output(self) -> None:
        with self.assertRaisesRegex(Exception, "JSON"):
            extract_json("plain text")

    def test_applies_context_correction_without_changing_timeline(self) -> None:
        segments = [
            TranscriptSegment(0, 2, "hello"),
            TranscriptSegment(2, 4, "walker aar"),
        ]
        organization = OrganizedVideo(
            short_description="这是一段用于验证字幕校订结果的视频说明。",
            summary="这是一段足够长且具体的摘要，用于验证字幕校订不会改变原有时间轴信息。",
            tags=["字幕", "校订", "测试"],
            chapters=[
                OrganizedChapter(
                    title="字幕校订测试",
                    start_seconds=0,
                    end_seconds=4,
                    summary="检查低置信字幕是否被正确替换。",
                )
            ],
            subtitle_corrections=[
                OrganizedSubtitleCorrection(index=1, text="work with our")
            ],
        )

        result = apply_organization_corrections(segments, organization)

        self.assertEqual(result[1].text, "work with our")
        self.assertEqual((result[1].start, result[1].end), (2, 4))

    def test_discards_ai_rewrite_that_is_too_different_from_asr(self) -> None:
        segments = [TranscriptSegment(0, 4, "火把电灯等常规照明方式失效。")]
        organization = OrganizedVideo(
            short_description="这是一段用于测试字幕校订保护的中文视频。",
            summary="视频说明永夜环境下常规照明方式失效，并介绍居民面对黑暗时的处境。",
            tags=["永夜", "照明", "测试"],
            chapters=[
                OrganizedChapter(
                    title="照明失效",
                    start_seconds=0,
                    end_seconds=4,
                    summary="介绍常规照明方式在永夜中失效。",
                )
            ],
            subtitle_corrections=[
                OrganizedSubtitleCorrection(
                    index=0,
                    text="这是一段完全不同的内容，模型不应把字幕改写成一段宽泛摘要。",
                )
            ],
        )

        result = apply_organization_corrections(segments, organization)

        self.assertEqual(result[0].text, segments[0].text)

    def test_applies_short_term_mapping_without_rewriting_sentence(self) -> None:
        segments = [TranscriptSegment(0, 3, "世界居住着人类、精灵、爱人和兽人。")]
        organization = OrganizedVideo(
            short_description="这是一段用于验证专有名词映射的视频说明。",
            summary="这是一段足够长且具体的摘要，用于验证短词映射不会改写整句字幕内容。",
            tags=["字幕", "专名", "测试"],
            chapters=[
                OrganizedChapter(
                    title="专名映射测试",
                    start_seconds=0,
                    end_seconds=3,
                    summary="检查同音专有名词是否被准确替换。",
                )
            ],
            term_corrections=[
                OrganizedTermCorrection(source="爱人", target="矮人")
            ],
        )

        result = apply_organization_corrections(segments, organization)

        self.assertEqual(result[0].text, "世界居住着人类、精灵、矮人和兽人。")

    def test_empty_transcript_is_rejected_before_ai_request(self) -> None:
        from app.integrations.minimax import build_minimax_result

        with self.assertRaisesRegex(ValueError, "没有识别到语音"):
            build_minimax_result(
                video_id="empty-video",
                duration_seconds=10,
                segments=[],
                language="zh",
                language_probability=0.2,
                asr_model="faster-whisper tiny",
            )

    def test_retries_once_when_ai_json_is_truncated(self) -> None:
        truncated = Mock()
        truncated.raise_for_status.return_value = None
        truncated.json.return_value = {
            "choices": [{"message": {"content": '{"short_description":"未完成"'}}]
        }
        complete = Mock()
        complete.raise_for_status.return_value = None
        complete.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段完整的视频内容简介，满足长度要求。",'
                            '"summary":"这是一段完整且具体的视频摘要，用于验证截断响应只重试一次并成功恢复。",'
                            '"tags":["字幕","摘要","测试"],"subtitle_corrections":[],'
                            '"chapters":[{"title":"完整结果","start_seconds":0,'
                            '"end_seconds":4,"summary":"成功返回完整的结构化结果。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch(
                "app.integrations.minimax.httpx.post",
                side_effect=[truncated, complete],
            ) as post,
        ):
            result = request_organization(
                [TranscriptSegment(0, 4, "test subtitle")],
                4,
                set(),
            )

        self.assertEqual(result.chapters[0].title, "完整结果")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["max_completion_tokens"], 16_384)
        self.assertEqual(
            post.call_args_list[0].kwargs["json"]["thinking"],
            {"type": "disabled"},
        )
        self.assertEqual(post.call_args_list[1].kwargs["json"]["max_completion_tokens"], 32_768)

    def test_retries_once_when_ai_json_fails_schema_validation(self) -> None:
        invalid = Mock()
        invalid.raise_for_status.return_value = None
        invalid.json.return_value = {
            "choices": [{"message": {"content": '{"short_description":"太短"}'}}]
        }
        repaired = Mock()
        repaired.raise_for_status.return_value = None
        repaired.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段修复后的完整视频内容简介。",'
                            '"summary":"这是根据原字幕修复字段约束后的完整摘要，内容具体且长度符合要求。",'
                            '"tags":["字幕","结构化输出","修复"],'
                            '"chapters":[{"title":"结构修复","start_seconds":0,'
                            '"end_seconds":4,"summary":"修复字段约束后返回合法结果。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch("app.integrations.minimax.httpx.post", side_effect=[invalid, repaired]) as post,
        ):
            result = request_organization(
                [TranscriptSegment(0, 4, "测试字幕")],
                4,
                set(),
            )

        self.assertEqual(result.chapters[0].title, "结构修复")
        repair_messages = post.call_args_list[1].kwargs["json"]["messages"]
        self.assertIn("未通过结构校验", repair_messages[-1]["content"])

    def test_retries_when_chapters_do_not_cover_video(self) -> None:
        undercovered = Mock()
        undercovered.raise_for_status.return_value = None
        undercovered.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段完整的视频内容简介，满足长度要求。",'
                            '"summary":"这是一段完整且具体的视频摘要，但第一次返回的章节没有覆盖后半段。",'
                            '"tags":["章节","覆盖","测试"],'
                            '"chapters":[{"title":"前半段","start_seconds":0,'
                            '"end_seconds":40,"summary":"当前只覆盖了视频前半段内容。"}]}'
                        )
                    }
                }
            ]
        }
        repaired = Mock()
        repaired.raise_for_status.return_value = None
        repaired.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段修复章节覆盖范围的视频内容简介。",'
                            '"summary":"修复后的章节时间轴覆盖视频主要内容，并延伸到接近视频结尾的位置。",'
                            '"tags":["章节","覆盖","修复"],'
                            '"chapters":[{"title":"完整内容","start_seconds":0,'
                            '"end_seconds":100,"summary":"章节已经覆盖到视频结尾。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch(
                "app.integrations.minimax.httpx.post",
                side_effect=[undercovered, repaired],
            ) as post,
        ):
            result = request_organization(
                [TranscriptSegment(0, 100, "完整视频字幕")],
                100,
                set(),
            )

        self.assertEqual(result.chapters[-1].end_seconds, 100)
        self.assertEqual(post.call_count, 2)

    def test_discards_overlong_term_correction_before_schema_validation(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段完整的视频内容简介，满足长度要求。",'
                            '"summary":"这是一段完整且具体的视频摘要，用于验证无效术语不会拖垮合法结果。",'
                            '"tags":["字幕","术语","测试"],'
                            '"term_corrections":[{"source":"这是超过十二个字的错误术语字段",'
                            '"target":"正确术语"}],'
                            '"chapters":[{"title":"安全整理","start_seconds":0,'
                            '"end_seconds":4,"summary":"合法摘要与章节可以正常保留。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch("app.integrations.minimax.httpx.post", return_value=response),
        ):
            result = request_organization(
                [TranscriptSegment(0, 4, "原始字幕")],
                4,
                set(),
            )

        self.assertEqual(result.term_corrections, [])

    def test_accepts_sixteen_chapters_for_long_video(self) -> None:
        chapters = [
            OrganizedChapter(
                title=f"长视频章节 {index + 1}",
                start_seconds=index * 120,
                end_seconds=(index + 1) * 120,
                summary=f"这是长视频第 {index + 1} 个章节的具体内容说明。",
            )
            for index in range(16)
        ]

        result = OrganizedVideo(
            short_description="这是一段包含多个独立主题的长视频内容说明。",
            summary="这是一段超过三十分钟的长视频，因此需要保留足够多的章节才能准确覆盖不同主题。",
            tags=["长视频", "自动章节", "内容整理"],
            chapters=chapters,
        )

        self.assertEqual(len(result.chapters), 16)

    def test_discards_correction_for_unmarked_subtitle(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段完整的视频内容简介，满足长度要求。",'
                            '"summary":"这是一段完整且具体的视频摘要，用于验证越权字幕校订会被安全丢弃。",'
                            '"tags":["字幕","校订","测试"],'
                            '"subtitle_corrections":[{"index":1,"text":"不应采用的修改"}],'
                            '"chapters":[{"title":"安全校订","start_seconds":0,'
                            '"end_seconds":4,"summary":"保留合法整理结果并丢弃越权修改。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch("app.integrations.minimax.httpx.post", return_value=response),
        ):
            result = request_organization(
                [TranscriptSegment(0, 2, "first"), TranscriptSegment(2, 4, "second")],
                4,
                {0},
            )

        self.assertEqual(result.subtitle_corrections, [])

    def test_discards_overlong_unmarked_correction_before_schema_validation(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"short_description":"这是一段完整的视频内容简介，满足长度要求。",'
                            '"summary":"这是一段完整且具体的视频摘要，用于验证无效长校订不会拖垮合法结果。",'
                            '"tags":["字幕","校订","测试"],'
                            f'"subtitle_corrections":[{{"index":0,"text":"{"错" * 600}"}}],'
                            '"chapters":[{"title":"安全校订","start_seconds":0,'
                            '"end_seconds":4,"summary":"合法摘要与章节可以正常保留。"}]}'
                        )
                    }
                }
            ]
        }

        with (
            patch("app.integrations.minimax.MINIMAX_API_KEY", "test-key"),
            patch("app.integrations.minimax.httpx.post", return_value=response),
        ):
            result = request_organization(
                [TranscriptSegment(0, 4, "原始字幕")],
                4,
                set(),
            )

        self.assertEqual(result.subtitle_corrections, [])


if __name__ == "__main__":
    unittest.main()
