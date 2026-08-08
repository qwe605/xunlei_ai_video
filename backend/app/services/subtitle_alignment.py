"""用独立参考字幕校准 AI 字幕时间轴，不改写 ASR 识别文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.content_analysis import TranscriptSegment, vtt_timestamp


@dataclass(frozen=True)
class AlignmentResult:
    segments: list[TranscriptSegment]
    scores: list[float]
    low_confidence_indexes: list[int]


@dataclass(frozen=True)
class _Candidate:
    start: float
    end: float
    score: float
    ranking_score: float


_NUMBER_REPLACEMENTS = {
    "两千": "2000",
    "二千": "2000",
    "一千": "1000",
    "四百": "400",
    "三月": "3月",
    "四月": "4月",
}


def normalize_alignment_text(value: str) -> str:
    """消除不影响语义匹配的字形差异，原字幕文字本身保持不变。"""
    normalized = value.lower()
    for source, target in _NUMBER_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


def _time_at_character(
    references: list[TranscriptSegment],
    normalized_texts: list[str],
    character_index: int,
    *,
    is_end: bool,
) -> float:
    cursor = 0
    for reference, text in zip(references, normalized_texts, strict=True):
        next_cursor = cursor + len(text)
        if character_index < next_cursor:
            ratio = (character_index - cursor) / max(1, len(text))
            return reference.start + (reference.end - reference.start) * ratio
        if character_index == next_cursor and is_end:
            return reference.end
        cursor = next_cursor
    return references[-1].end


def _candidate_for_window(
    ai_segment: TranscriptSegment,
    references: list[TranscriptSegment],
) -> _Candidate | None:
    ai_text = normalize_alignment_text(ai_segment.text)
    reference_texts = [normalize_alignment_text(item.text) for item in references]
    joined = "".join(reference_texts)
    if not ai_text or not joined:
        return None

    score = SequenceMatcher(None, ai_text, joined, autojunk=False).ratio()
    occurrence = joined.find(ai_text)
    if occurrence >= 0:
        score = 1.0
        start = _time_at_character(references, reference_texts, occurrence, is_end=False)
        end = _time_at_character(
            references,
            reference_texts,
            occurrence + len(ai_text),
            is_end=True,
        )
    else:
        reverse_occurrence = ai_text.find(joined)
        if reverse_occurrence >= 0:
            score = max(score, len(joined) / len(ai_text))
        start = references[0].start
        end = references[-1].end

    original_center = (ai_segment.start + ai_segment.end) / 2
    target_center = (start + end) / 2
    time_penalty = min(0.18, abs(target_center - original_center) * 0.015)
    return _Candidate(start, end, score, score - time_penalty)


def _best_candidate(
    ai_segment: TranscriptSegment,
    references: list[TranscriptSegment],
    *,
    search_radius_seconds: float,
    max_reference_cues: int,
) -> _Candidate | None:
    center = (ai_segment.start + ai_segment.end) / 2
    nearby = [
        index
        for index, item in enumerate(references)
        if item.end >= center - search_radius_seconds
        and item.start <= center + search_radius_seconds
    ]
    candidates: list[_Candidate] = []
    for start_index in nearby:
        for size in range(1, max_reference_cues + 1):
            window = references[start_index : start_index + size]
            if not window:
                continue
            candidate = _candidate_for_window(ai_segment, window)
            if candidate is not None:
                candidates.append(candidate)
    return max(candidates, key=lambda item: item.ranking_score, default=None)


def _interpolated_shift(
    index: int,
    segments: list[TranscriptSegment],
    anchors: dict[int, _Candidate],
) -> float:
    previous = max((item for item in anchors if item < index), default=None)
    following = min((item for item in anchors if item > index), default=None)

    def shift(anchor_index: int) -> float:
        original = segments[anchor_index]
        target = anchors[anchor_index]
        return (target.start + target.end - original.start - original.end) / 2

    if previous is None and following is None:
        return 0.0
    if previous is None:
        return shift(following)  # type: ignore[arg-type]
    if following is None:
        return shift(previous)
    distance = following - previous
    ratio = (index - previous) / distance
    return shift(previous) * (1 - ratio) + shift(following) * ratio


def _copy_with_timing(
    segment: TranscriptSegment,
    start: float,
    end: float,
) -> TranscriptSegment:
    return TranscriptSegment(
        start=max(0.0, start),
        end=max(max(0.0, start) + 0.08, end),
        text=segment.text,
        avg_logprob=segment.avg_logprob,
        no_speech_prob=segment.no_speech_prob,
        compression_ratio=segment.compression_ratio,
        min_word_probability=segment.min_word_probability,
        low_confidence_word_ratio=segment.low_confidence_word_ratio,
        words=segment.words,
    )


def align_subtitle_timing(
    segments: list[TranscriptSegment],
    references: list[TranscriptSegment],
    *,
    minimum_score: float = 0.55,
    search_radius_seconds: float = 10.0,
    max_reference_cues: int = 5,
) -> AlignmentResult:
    """按文本相似度寻找时间锚点，再为未匹配字幕插值并消除重叠。"""
    ordered_references = sorted(references, key=lambda item: (item.start, item.end))
    anchors: dict[int, _Candidate] = {}
    scores: list[float] = []
    for index, segment in enumerate(segments):
        candidate = _best_candidate(
            segment,
            ordered_references,
            search_radius_seconds=search_radius_seconds,
            max_reference_cues=max_reference_cues,
        )
        score = candidate.score if candidate is not None else 0.0
        scores.append(score)
        if candidate is not None and score >= minimum_score:
            anchors[index] = candidate

    aligned: list[TranscriptSegment] = []
    for index, segment in enumerate(segments):
        if index in anchors:
            candidate = anchors[index]
            aligned.append(_copy_with_timing(segment, candidate.start, candidate.end))
        else:
            shift = _interpolated_shift(index, segments, anchors)
            aligned.append(
                _copy_with_timing(segment, segment.start + shift, segment.end + shift)
            )

    # 多条 AI 字幕可能命中同一条参考字幕。仅在重叠时用中心中点切边界，
    # 参考字幕原本存在的静音空白会被完整保留。
    for index in range(1, len(aligned)):
        previous = aligned[index - 1]
        current = aligned[index]
        if current.start >= previous.end:
            continue
        previous_center = (previous.start + previous.end) / 2
        current_center = (current.start + current.end) / 2
        boundary = (previous_center + current_center) / 2
        boundary = max(previous.start + 0.08, min(boundary, current.end - 0.08))
        aligned[index - 1] = _copy_with_timing(previous, previous.start, boundary)
        aligned[index] = _copy_with_timing(current, boundary, current.end)

    return AlignmentResult(
        segments=aligned,
        scores=scores,
        low_confidence_indexes=[index for index in range(len(segments)) if index not in anchors],
    )


def render_aligned_vtt(segments: list[TranscriptSegment]) -> str:
    """渲染已成型字幕，禁止再次合并、拆分或改写文本。"""
    lines = ["WEBVTT", "", "NOTE 由当前配置的纯音频 ASR 链路生成", ""]
    for index, segment in enumerate(segments, start=1):
        lines.extend(
            [
                str(index),
                f"{vtt_timestamp(segment.start)} --> {vtt_timestamp(segment.end)}",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines)
