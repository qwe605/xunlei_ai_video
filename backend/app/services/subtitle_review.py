import re

from app.services.content_analysis import TranscriptSegment, normalize_text


MAX_REVIEW_SEGMENTS = 16


def suspicion_score(segment: TranscriptSegment) -> float:
    """综合逐词与整句信号，只标记需要 M3 结合上下文关注的字幕。"""
    score = 0.0
    if segment.avg_logprob < -0.55:
        score += min(2.0, (-0.55 - segment.avg_logprob) * 2.5)
    if segment.no_speech_prob > 0.35:
        score += min(1.5, (segment.no_speech_prob - 0.35) * 2.5)
    if segment.compression_ratio > 2.2:
        score += min(1.5, (segment.compression_ratio - 2.2) * 1.5)
    if segment.min_word_probability < 0.35:
        score += min(1.2, (0.35 - segment.min_word_probability) * 2.5 + 0.4)
    if segment.low_confidence_word_ratio >= 0.2:
        score += min(1.0, segment.low_confidence_word_ratio * 1.5)

    text = normalize_text(segment.text)
    if len(text) <= 2:
        score += 0.8
    if re.search(r"(.)\1{4,}", text):
        score += 1.0
    return score


def select_suspicious_segments(
    segments: list[TranscriptSegment],
    limit: int = MAX_REVIEW_SEGMENTS,
    *,
    review_all: bool = False,
) -> list[int]:
    # 中文句段已随摘要在同一次请求中发送；全量标记不会增加网络往返，只开放保守校订权限。
    if review_all:
        return list(range(min(len(segments), max(0, limit))))
    ranked = [
        (suspicion_score(segment), index)
        for index, segment in enumerate(segments)
        if suspicion_score(segment) >= 0.35
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return sorted(index for _, index in ranked[: max(0, limit)])
