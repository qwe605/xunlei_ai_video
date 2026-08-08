import json
import re
from difflib import SequenceMatcher

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.config import MINIMAX_API_KEY, MINIMAX_BASE_URL, MINIMAX_MODEL
from app.schemas import AnalysisResult, ChapterResult
from app.services.content_analysis import TranscriptSegment, build_vtt
from app.services.text_normalization import simplify_data, to_simplified_chinese


class OrganizedChapter(BaseModel):
    title: str = Field(min_length=2, max_length=40)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    summary: str = Field(min_length=6, max_length=240)


class OrganizedSubtitleCorrection(BaseModel):
    index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=500)


class OrganizedTermCorrection(BaseModel):
    source: str = Field(min_length=1, max_length=12)
    target: str = Field(min_length=1, max_length=12)


class OrganizedVideo(BaseModel):
    short_description: str = Field(min_length=12, max_length=120)
    summary: str = Field(min_length=30, max_length=700)
    tags: list[str] = Field(min_length=3, max_length=8)
    chapters: list[OrganizedChapter] = Field(min_length=1, max_length=24)
    subtitle_corrections: list[OrganizedSubtitleCorrection] = Field(
        default_factory=list,
        max_length=64,
    )
    term_corrections: list[OrganizedTermCorrection] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_chapter_order(self) -> "OrganizedVideo":
        for index, chapter in enumerate(self.chapters):
            if chapter.start_seconds >= chapter.end_seconds:
                raise ValueError("章节结束时间必须晚于开始时间")
            if index and chapter.start_seconds < self.chapters[index - 1].start_seconds:
                raise ValueError("章节必须按开始时间排序")
        return self


class MinimaxSummaryError(Exception):
    pass


def normalize_for_comparison(value: str) -> str:
    """比较校订前后文字时忽略空白和标点，只衡量实际内容变化。"""
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", value).lower()


def timestamp(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def transcript_for_prompt(
    segments: list[TranscriptSegment],
    suspicious_indexes: set[int] | None = None,
) -> str:
    suspicious = suspicious_indexes or set()
    lines = [
        (
            f"[index={index} {timestamp(segment.start)}-{timestamp(segment.end)}"
            f"{' 待复核' if index in suspicious else ''}] {segment.text.strip()}"
        )
        for index, segment in enumerate(segments)
    ]
    # M3 上下文足够大，但仍限制单次发送，避免异常长视频造成不必要费用。
    return "\n".join(lines)[:80_000]


def extract_json(content: str) -> dict:
    without_thinking = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", without_thinking, flags=re.DOTALL)
    candidate = fenced.group(1) if fenced else without_thinking
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise MinimaxSummaryError("MiniMax 未返回可解析的 JSON")
    try:
        value = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as error:
        raise MinimaxSummaryError("MiniMax 返回的 JSON 格式不完整") from error
    if not isinstance(value, dict):
        raise MinimaxSummaryError("MiniMax 返回结果不是对象")
    return value


def request_organization(
    segments: list[TranscriptSegment],
    duration_seconds: float,
    suspicious_indexes: set[int] | None = None,
) -> OrganizedVideo:
    if not MINIMAX_API_KEY:
        raise MinimaxSummaryError("MiniMax API Key 未配置")

    system_prompt = """
你是视频内容编辑。只根据用户提供的带时间轴字幕整理视频，不得补充字幕之外的事实。
输出必须是单个 JSON 对象，不要 Markdown，不要解释，不要思考过程。
所有标题、摘要和标签使用简体中文；专有名词可以保留原文。
章节必须覆盖视频主要内容，按开始时间升序，时间不得超过视频总时长。
章节数量应匹配视频长度：10 分钟内通常 3 至 8 个，30 分钟以上通常 8 至 20 个，
最多不得超过 24 个；不要为了减少数量而合并明显不同的主题。
保持输出紧凑：short_description 不超过 80 字，summary 不超过 500 字，
章节 title 不超过 24 字，每个章节 summary 不超过 100 字。
subtitle_corrections 只填写确有必要修改的单句字幕，优先修正结合上下文能够确定的
同音错字、专有名词、错误标点和断句造成的词语割裂；不得润色表达，禁止复制上下文或整段转录。
term_corrections 用于全片反复出现且能根据上下文确定的短词纠错，只返回原词到正确词的
精确映射，例如 {"source":"爱人","target":"矮人"}；禁止填写完整句子。
JSON 格式：
{
  "short_description": "一句话说明视频讲什么",
  "summary": "连贯、具体的整片摘要",
  "tags": ["3至8个关键词"],
  "subtitle_corrections": [
    {"index": 2, "text": "校订后的原语言字幕"}
  ],
  "term_corrections": [
    {"source": "ASR 中的错误短词", "target": "校订后的专有名词"}
  ],
  "chapters": [
    {
      "title": "具体章节标题，禁止使用第1段或关键词堆砌",
      "start_seconds": 0,
      "end_seconds": 60,
      "summary": "本章具体讲了什么"
    }
  ]
}
""".strip()
    user_prompt = (
        f"视频总时长：{duration_seconds:.2f} 秒。\n"
        "以下是 ASR 字幕。仅可在 subtitle_corrections 中校订标有“待复核”的字幕；"
        "不要翻译、扩写或修改其他字幕，无法确定时不要返回该项。"
        "摘要和章节仍须严格依据字幕，不得虚构：\n"
        f"{transcript_for_prompt(segments, suspicious_indexes)}"
    )
    allowed_corrections = suspicious_indexes or set()
    transcript_text = "\n".join(segment.text for segment in segments)
    last_response_content = ""
    last_validation_error: MinimaxSummaryError | None = None
    for completion_limit in (16_384, 32_768):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if last_validation_error and last_response_content:
            messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": last_response_content[-20_000:],
                    },
                    {
                        "role": "user",
                        "content": (
                            "上一个 JSON 未通过结构校验。请仅修正字段长度、数量、类型、"
                            "章节顺序或时间范围，不要改变事实；仍只返回一个 JSON 对象。"
                            f"校验错误：{last_validation_error}"
                        ),
                    },
                ]
            )
        try:
            response = httpx.post(
                f"{MINIMAX_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {MINIMAX_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MINIMAX_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_completion_tokens": completion_limit,
                    "thinking": {"type": "disabled"},
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise MinimaxSummaryError("MiniMax 请求失败，请检查网络、额度或 API Key") from error

        status_code = payload.get("base_resp", {}).get("status_code", 0)
        if status_code not in (0, None):
            raise MinimaxSummaryError("MiniMax 拒绝了本次内容整理请求")
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise MinimaxSummaryError("MiniMax 响应缺少正文") from error

        last_response_content = str(content)
        try:
            parsed = simplify_data(extract_json(last_response_content))
            if isinstance(parsed.get("tags"), list):
                parsed["tags"] = parsed["tags"][:8]
            if isinstance(parsed.get("chapters"), list):
                parsed["chapters"] = parsed["chapters"][:24]

            # 先过滤越权或超长校订，再进入 Pydantic；一个坏项不应拖垮合法摘要和章节。
            raw_corrections = parsed.get("subtitle_corrections", [])
            parsed["subtitle_corrections"] = [
                correction
                for correction in raw_corrections
                if isinstance(correction, dict)
                and correction.get("index") in allowed_corrections
                and isinstance(correction.get("text"), str)
                and 1 <= len(correction["text"]) <= 500
            ]
            raw_terms = parsed.get("term_corrections", [])
            parsed["term_corrections"] = [
                correction
                for correction in raw_terms
                if isinstance(correction, dict)
                and isinstance(correction.get("source"), str)
                and isinstance(correction.get("target"), str)
                and 1 <= len(correction["source"]) <= 12
                and 1 <= len(correction["target"]) <= 12
            ][:20]
            organization = OrganizedVideo.model_validate(parsed)
            for chapter in organization.chapters:
                if chapter.end_seconds > duration_seconds + 1:
                    raise MinimaxSummaryError("章节结束时间超出视频总时长")
            if organization.chapters[-1].end_seconds < duration_seconds * 0.85:
                raise MinimaxSummaryError(
                    "章节覆盖不足：最后章节结束时间必须接近视频结尾，"
                    f"当前为 {organization.chapters[-1].end_seconds:.2f} 秒，"
                    f"视频总时长为 {duration_seconds:.2f} 秒"
                )
        except ValidationError as error:
            details = error.errors(include_url=False, include_input=False)
            last_validation_error = MinimaxSummaryError(
                "字段校验失败：" + json.dumps(details[:6], ensure_ascii=False)
            )
            continue
        except MinimaxSummaryError as error:
            last_validation_error = error
            continue

        return organization.model_copy(
            update={
                "term_corrections": [
                    correction
                    for correction in organization.term_corrections
                    if correction.source in transcript_text
                    and correction.source != correction.target
                    and abs(len(correction.source) - len(correction.target)) <= 2
                ]
            }
        )

    raise last_validation_error or MinimaxSummaryError("MiniMax 未返回完整结果")


def apply_organization_corrections(
    segments: list[TranscriptSegment],
    organization: OrganizedVideo,
) -> list[TranscriptSegment]:
    replacements: dict[int, str] = {}
    for correction in organization.subtitle_corrections:
        if correction.index >= len(segments):
            continue
        source = normalize_for_comparison(segments[correction.index].text)
        target = normalize_for_comparison(correction.text)
        # 允许纠正同音字和断句，但拒绝把字幕整句改写成摘要或补写字幕外事实。
        contains_chinese = bool(re.search(r"[\u4e00-\u9fff]", source + target))
        is_conservative = SequenceMatcher(None, source, target).ratio() >= 0.55
        if source and target and (not contains_chinese or is_conservative):
            replacements[correction.index] = correction.text.strip()
    term_replacements = {
        correction.source: correction.target
        for correction in organization.term_corrections
    }
    corrected: list[TranscriptSegment] = []
    for index, segment in enumerate(segments):
        text = replacements.get(index, segment.text)
        for source, target in term_replacements.items():
            text = text.replace(source, target)
        corrected.append(
            TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=to_simplified_chinese(text),
                avg_logprob=segment.avg_logprob,
                no_speech_prob=segment.no_speech_prob,
                compression_ratio=segment.compression_ratio,
                min_word_probability=segment.min_word_probability,
                low_confidence_word_ratio=segment.low_confidence_word_ratio,
                words=segment.words,
            )
        )
    return corrected


def build_minimax_result(
    *,
    video_id: str,
    duration_seconds: float,
    segments: list[TranscriptSegment],
    language: str,
    language_probability: float,
    asr_model: str,
    suspicious_indexes: set[int] | None = None,
) -> AnalysisResult:
    if not segments:
        raise ValueError("没有识别到语音，请确认视频包含清晰音轨")
    organization = request_organization(segments, duration_seconds, suspicious_indexes)
    corrected_segments = apply_organization_corrections(segments, organization)
    confidence = min(0.99, max(0.55, language_probability))
    chapters = [
        ChapterResult(
            id=f"{video_id}-chapter-{index}",
            title=chapter.title,
            start_seconds=chapter.start_seconds,
            end_seconds=min(duration_seconds, chapter.end_seconds),
            summary=chapter.summary,
            confidence=confidence,
        )
        for index, chapter in enumerate(organization.chapters, start=1)
    ]
    return AnalysisResult(
        language=language,
        confidence=confidence,
        short_description=organization.short_description,
        summary=organization.summary,
        tags=organization.tags,
        subtitles_vtt=build_vtt(corrected_segments),
        asr_model=f"{asr_model} + {MINIMAX_MODEL}",
        subtitle_correction_count=(
            len(organization.subtitle_corrections) + len(organization.term_corrections)
        ),
        chapters=chapters,
    )
