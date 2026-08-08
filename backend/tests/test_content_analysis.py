import re
import unittest

from app.services.content_analysis import (
    TranscriptWord,
    TranscriptSegment,
    build_analysis_result,
    build_vtt,
    coalesce_caption_segments,
    extract_keywords,
    prepare_segments_for_review,
    split_long_caption_segments,
)


class ContentAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.segments = [
            TranscriptSegment(0, 8, "Python can catch a value error with an except block."),
            TranscriptSegment(8, 16, "A second except handles zero division errors."),
            TranscriptSegment(16, 24, "Different errors can display different messages."),
        ]

    def test_builds_valid_timed_result(self) -> None:
        result = build_analysis_result(
            video_id="video-1",
            duration_seconds=24,
            segments=self.segments,
            language="en",
            language_probability=0.96,
            model_name="tiny",
        )

        self.assertEqual(result.language, "en")
        self.assertEqual(len(result.chapters), 1)
        self.assertEqual(result.chapters[0].end_seconds, 24)
        self.assertIn("WEBVTT", result.subtitles_vtt)
        self.assertIn("00:00:08.000", result.subtitles_vtt)

    def test_keywords_exclude_common_words(self) -> None:
        keywords = extract_keywords("the error and the error with python")
        self.assertEqual(keywords[:2], ["error", "python"])

    def test_empty_segments_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有识别到语音"):
            build_analysis_result(
                video_id="video-1",
                duration_seconds=10,
                segments=[],
                language="en",
                language_probability=0.5,
                model_name="tiny",
            )

    def test_vtt_normalizes_whitespace(self) -> None:
        vtt = build_vtt([TranscriptSegment(1.2, 2.4, "  hello   world ")])
        self.assertIn("00:00:01.200 --> 00:00:02.400", vtt)
        self.assertIn("hello world", vtt)

    def test_vtt_merges_short_chinese_fragments_without_rewriting_text(self) -> None:
        segments = [
            TranscriptSegment(0.0, 1.0, "这个世界居住着人类、"),
            TranscriptSegment(1.1, 1.8, "精灵、"),
            TranscriptSegment(1.9, 2.6, "矮人和兽人。"),
            TranscriptSegment(3.0, 4.0, "永夜降临。"),
        ]

        merged = coalesce_caption_segments(segments)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].text, "这个世界居住着人类、精灵、矮人和兽人。")
        self.assertEqual((merged[0].start, merged[0].end), (0.0, 2.6))

    def test_review_preparation_repairs_contiguous_orphan_fragment(self) -> None:
        segments = [
            TranscriptSegment(36.01, 40.45, "太阳未能升起，世界陷入永夜，火把电。"),
            TranscriptSegment(40.45, 41.07, "灯等。"),
            TranscriptSegment(41.07, 45.91, "常规照明方式失效，只剩月光能够略微照明。"),
        ]

        prepared = prepare_segments_for_review(segments)

        self.assertEqual(len(prepared), 2)
        self.assertEqual(
            prepared[0].text,
            "太阳未能升起，世界陷入永夜，火把电灯等。",
        )
        self.assertEqual((prepared[0].start, prepared[-1].end), (36.01, 45.91))

    def test_review_preparation_keeps_complete_asr_sentence_boundaries(self) -> None:
        segments = [
            TranscriptSegment(68.89, 70.03, "只剩一颗龙蛋幸存。"),
            TranscriptSegment(70.25, 71.45, "死后力量凝聚的遗蜕。"),
            TranscriptSegment(71.67, 73.21, "也成为了各族持有的神器。"),
        ]

        prepared = prepare_segments_for_review(segments)

        self.assertEqual(prepared, segments)
        self.assertEqual([item.start for item in prepared], [68.89, 70.25, 71.67])

    def test_vtt_splits_long_chinese_caption_at_punctuation(self) -> None:
        segments = [
            TranscriptSegment(
                0,
                12,
                "太阳不再升起，世界陷入永夜。火把和电灯失效，只剩月光能够略微照明。居民开始走上街道，表达对末日的恐惧。",
            )
        ]

        vtt = build_vtt(segments)

        self.assertGreater(vtt.count(" --> "), 1)
        cues = [
            line
            for line in vtt.splitlines()
            if " --> " not in line
            and line
            and not line.isdigit()
            and not line.startswith("WEBVTT")
            and not line.startswith("NOTE")
        ]
        self.assertTrue(all(len(line) <= 20 for line in cues))
        self.assertTrue(all(not re.search(r"[，。！？；：、,.!?;:]", line) for line in cues))

    def test_vtt_uses_punctuation_to_split_but_hides_it_from_display(self) -> None:
        vtt = build_vtt(
            [TranscriptSegment(0, 6, "永夜降临，太阳不再升起。居民走上街道，城市陷入混乱！")]
        )
        cue_texts = [
            line
            for line in vtt.splitlines()
            if line and not line.isdigit() and " --> " not in line and not line.startswith(("WEBVTT", "NOTE"))
        ]

        self.assertGreaterEqual(len(cue_texts), 2)
        self.assertEqual("".join(cue_texts), "永夜降临太阳不再升起居民走上街道城市陷入混乱")

    def test_vtt_uses_list_separator_without_splitting_noun_phrase(self) -> None:
        vtt = build_vtt(
            [
                TranscriptSegment(
                    0,
                    8,
                    "分别为守护之龙的骑士命途、隐匿之龙的刺客命途、智慧之龙的学者命途以及誓约之龙的士兵命途。",
                )
            ]
        )
        cue_texts = [line for line in vtt.splitlines() if line and not line.isdigit()]

        self.assertFalse(any(line.endswith("智慧") for line in cue_texts))
        self.assertFalse(any(line.startswith("之龙") for line in cue_texts))

    def test_vtt_prefers_connector_boundary_over_fixed_width_cut(self) -> None:
        vtt = build_vtt(
            [
                TranscriptSegment(
                    0,
                    6,
                    "其中诞生的幼龙若是能触碰到所有神器并完成对应仪式，即可让光明重回大地。",
                )
            ]
        )
        cue_texts = [line for line in vtt.splitlines() if line and not line.isdigit()]

        self.assertFalse(any(line.endswith("完成") for line in cue_texts))
        self.assertFalse(any(line.startswith("对应仪式") for line in cue_texts))

    def test_vtt_does_not_split_chinese_connector_inside_word(self) -> None:
        segments = [
            TranscriptSegment(
                0, 4, "使其成为了四族的守护者，并立下永远照亮世界的誓约。正"
            ),
            TranscriptSegment(
                4.2, 9, "因如此，为帮助文明更好地发展，烛龙赐予了凡人名为命途的超凡之力，"
            ),
            TranscriptSegment(9, 14, "分别为守护之龙的骑士命途、隐匿之龙的刺客命途。"),
        ]

        vtt = build_vtt(segments)
        cue_texts = [
            line
            for line in vtt.splitlines()
            if line and not line.isdigit() and " --> " not in line and not line.startswith("WEBVTT") and not line.startswith("NOTE")
        ]

        self.assertFalse(any(line.endswith("正") for line in cue_texts))
        self.assertFalse(any(line.startswith("因如此") for line in cue_texts))

    def test_vtt_keeps_last_dragon_noun_phrase_together(self) -> None:
        segments = [
            TranscriptSegment(
                0, 5, "不过获得智慧与人性后，烛龙有了寿命限制。此刻是世界历一千年，最后一只"
            ),
            TranscriptSegment(5.04, 8, "烛龙老死，只剩一颗龙蛋。"),
            TranscriptSegment(8, 12, "幸存烛龙的力量凝聚为各族持有的神器。"),
        ]

        vtt = build_vtt(segments)
        cue_texts = [line for line in vtt.splitlines() if line and not line.isdigit()]

        self.assertFalse(any(line.endswith("最后一只") for line in cue_texts))
        self.assertFalse(any(line.startswith("烛龙老死") for line in cue_texts))

    def test_word_timestamps_preserve_real_pause_when_splitting(self) -> None:
        segments = split_long_caption_segments(
            [
                TranscriptSegment(
                    0,
                    6,
                    "第一句话，第二句话",
                    words=(
                        TranscriptWord(0, 2, "第一句话"),
                        TranscriptWord(4, 6, "第二句话"),
                    ),
                )
            ],
            max_characters=5,
        )

        self.assertEqual([item.text for item in segments], ["第一句话，", "第二句话"])
        self.assertAlmostEqual(segments[0].end, 2.0)
        self.assertAlmostEqual(segments[1].start, 4.0)


if __name__ == "__main__":
    unittest.main()
