import math
import re
from collections import Counter
from dataclasses import dataclass

from app.schemas import AnalysisResult, ChapterResult


@dataclass(frozen=True)
class TranscriptWord:
    start: float
    end: float
    text: str
    probability: float = 1.0


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    compression_ratio: float = 1.0
    min_word_probability: float = 1.0
    low_confidence_word_ratio: float = 0.0
    words: tuple[TranscriptWord, ...] = ()


ENGLISH_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "but",
    "can",
    "could",
    "does",
    "for",
    "from",
    "have",
    "here",
    "into",
    "just",
    "like",
    "more",
    "not",
    "now",
    "one",
    "only",
    "our",
    "that",
    "the",
    "then",
    "there",
    "they",
    "this",
    "those",
    "through",
    "very",
    "was",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
    "you",
    "your",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    english = [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text)
        if word.lower() not in ENGLISH_STOP_WORDS
    ]
    chinese = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    ranked = [word for word, _ in Counter(english + chinese).most_common(limit)]
    return ranked or ["视频内容"]


def select_summary(segments: list[TranscriptSegment]) -> str:
    if not segments:
        return "没有识别到可用于摘要的语音内容。"

    sample_count = min(4, len(segments))
    positions = {
        min(len(segments) - 1, round(index * (len(segments) - 1) / max(1, sample_count - 1)))
        for index in range(sample_count)
    }
    selected = [normalize_text(segments[index].text) for index in sorted(positions)]
    summary = " ".join(part for part in selected if part)
    return summary[:900] or "已完成语音识别，但有效文本较少。"


def build_chapters(
    video_id: str,
    duration_seconds: float,
    segments: list[TranscriptSegment],
    confidence: float,
) -> list[ChapterResult]:
    chapter_count = min(6, max(1, math.ceil(duration_seconds / 120)))
    window = duration_seconds / chapter_count
    chapters: list[ChapterResult] = []

    for index in range(chapter_count):
        start = index * window
        end = duration_seconds if index == chapter_count - 1 else (index + 1) * window
        chapter_segments = [
            segment for segment in segments if segment.end > start and segment.start < end
        ]
        text = normalize_text(" ".join(segment.text for segment in chapter_segments))
        keywords = extract_keywords(text, 2)
        title = f"第 {index + 1} 段 · {' / '.join(keywords)}"
        summary = text[:420] or "该时间段没有识别到清晰语音。"
        chapters.append(
            ChapterResult(
                id=f"{video_id}-chapter-{index + 1}",
                title=title,
                start_seconds=round(start, 2),
                end_seconds=round(max(start + 0.01, end), 2),
                summary=summary,
                confidence=confidence,
            )
        )
    return chapters


def vtt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _join_caption_text(left: str, right: str) -> str:
    """中文转写直接拼接，英文单词边界保留一个空格。"""
    separator = " " if re.search(r"[A-Za-z0-9]$", left) and re.match(r"^[A-Za-z0-9]", right) else ""
    return normalize_text(f"{left}{separator}{right}")


CHINESE_SENTENCE_ENDINGS = "。！？!?"
CHINESE_CONTINUATION_WORDS = (
    "的",
    "地",
    "得",
    "和",
    "与",
    "及",
    "或",
    "等",
    "为",
    "在",
    "将",
    "把",
    "被",
    "使",
    "让",
    "因",
    "由",
    "从",
    "向",
    "到",
    "但",
    "而",
    "并",
    "且",
)

# 这些短语落在字幕末尾时，语义通常尚未结束。排版阶段仅把原文字移到下一条，
# 不修改 ASR 内容，避免出现“正｜因如此”“最后一只｜烛龙”一类断词。
CHINESE_TRAILING_BOUNDARY_PHRASES = (
    "最后一只",
    "最后一位",
    "最后一个",
    "正",
)

# 标点只参与语义切分，不进入最终屏幕字幕。保留连字符，避免破坏 MiniMax-M3、
# Python 等英文术语；空格同样保留给英文单词边界。
DISPLAY_PUNCTUATION_PATTERN = re.compile(r'[，。！？；：、,.!?;:"“”‘’（）()【】\[\]…—]')
MAX_DISPLAY_CAPTION_CHARACTERS = 20
MAX_DISPLAY_CAPTION_SECONDS = 4.5
CHINESE_BREAK_BEFORE_WORDS = (
    "正因如此",
    "并且",
    "以及",
    "因此",
    "所以",
    "不过",
    "但是",
    "好在",
    "随后",
    "其中",
    "即可",
    "若是",
    "并",
    "且",
    "但",
    "而",
)


def _chinese_character_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _ends_complete_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped or stripped[-1] not in CHINESE_SENTENCE_ENDINGS:
        return bool(re.search(r"[.!?]$", stripped))
    stem = stripped[:-1].rstrip()
    return not stem.endswith(CHINESE_CONTINUATION_WORDS)


def _join_continuation(left: str, right: str, *, remove_terminal: bool = False) -> str:
    normalized_left = normalize_text(left)
    if remove_terminal or not _ends_complete_sentence(normalized_left):
        normalized_left = re.sub(r"[。！？!?]+$", "", normalized_left)
    return _join_caption_text(normalized_left, normalize_text(right))


def prepare_segments_for_review(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """修复 VAD/标点模型产生的孤立短段，同时保留 ASR 原始停顿边界。

    这里不猜测新文字，只移动边界和移除被错误插入的句末标点。相邻短段必须几乎无
    静音间隔才会并入前句，避免把真正停顿后的独立短句强行拼接。MiniMax 请求本身已
    包含相邻字幕，不再把完整句合并成 30 秒大段后按字符比例重新切分。
    """
    repaired: list[TranscriptSegment] = []
    for segment in segments:
        text = normalize_text(segment.text)
        if not text:
            continue
        normalized = TranscriptSegment(
            start=segment.start,
            end=segment.end,
            text=text,
            avg_logprob=segment.avg_logprob,
            no_speech_prob=segment.no_speech_prob,
            compression_ratio=segment.compression_ratio,
            min_word_probability=segment.min_word_probability,
            low_confidence_word_ratio=segment.low_confidence_word_ratio,
            words=segment.words,
        )
        if not repaired:
            repaired.append(normalized)
            continue

        previous = repaired[-1]
        gap = normalized.start - previous.end
        is_orphan = (
            normalized.end - normalized.start <= 1.0
            or _chinese_character_count(normalized.text) <= 4
        )
        if is_orphan and gap <= 0.12:
            repaired[-1] = TranscriptSegment(
                start=previous.start,
                end=normalized.end,
                text=_join_continuation(previous.text, normalized.text, remove_terminal=True),
                avg_logprob=min(previous.avg_logprob, normalized.avg_logprob),
                no_speech_prob=max(previous.no_speech_prob, normalized.no_speech_prob),
                compression_ratio=max(previous.compression_ratio, normalized.compression_ratio),
                min_word_probability=min(
                    previous.min_word_probability,
                    normalized.min_word_probability,
                ),
                low_confidence_word_ratio=max(
                    previous.low_confidence_word_ratio,
                    normalized.low_confidence_word_ratio,
                ),
                words=previous.words + normalized.words,
            )
            continue
        repaired.append(normalized)

    return repaired


def _split_long_clause(text: str, max_characters: int) -> list[str]:
    """长分句优先在中文连接词前切开，找不到自然边界时才使用固定宽度。"""
    remaining = text
    chunks: list[str] = []
    minimum_chunk = max(6, max_characters // 2)
    while len(remaining) > max_characters:
        candidate_positions = [
            position
            for word in CHINESE_BREAK_BEFORE_WORDS
            for position in [remaining.find(word, minimum_chunk, max_characters + 1)]
            if position > 0
        ]
        split_at = max(candidate_positions, default=max_characters)
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _timing_for_groups(
    segment: TranscriptSegment,
    groups: list[str],
) -> list[tuple[float, float, tuple[TranscriptWord, ...]]]:
    """优先使用词级时间戳定位切句边界，保留词与词之间的真实静音。"""
    usable_words = [
        word
        for word in segment.words
        if word.end > word.start and DISPLAY_PUNCTUATION_PATTERN.sub("", word.text).strip()
    ]
    if not usable_words:
        duration = segment.end - segment.start
        total_characters = max(1, sum(len(group) for group in groups))
        cursor = segment.start
        result: list[tuple[float, float, tuple[TranscriptWord, ...]]] = []
        for index, group in enumerate(groups):
            end = (
                segment.end
                if index == len(groups) - 1
                else cursor + duration * len(group) / total_characters
            )
            result.append((cursor, end, ()))
            cursor = end
        return result

    word_lengths = [
        max(1, len(DISPLAY_PUNCTUATION_PATTERN.sub("", word.text).replace(" ", "")))
        for word in usable_words
    ]

    def time_at(character_index: int, *, is_end: bool) -> float:
        cursor = 0
        for word, length in zip(usable_words, word_lengths, strict=True):
            next_cursor = cursor + length
            if character_index < next_cursor:
                ratio = (character_index - cursor) / length
                return word.start + (word.end - word.start) * ratio
            if character_index == next_cursor and is_end:
                return word.end
            cursor = next_cursor
        return usable_words[-1].end

    group_lengths = [
        max(1, len(DISPLAY_PUNCTUATION_PATTERN.sub("", group).replace(" ", "")))
        for group in groups
    ]
    total_word_characters = sum(word_lengths)
    total_group_characters = max(1, sum(group_lengths))
    result = []
    group_cursor = 0
    for index, group_length in enumerate(group_lengths):
        start_character = round(group_cursor * total_word_characters / total_group_characters)
        group_cursor += group_length
        end_character = round(group_cursor * total_word_characters / total_group_characters)
        start = time_at(start_character, is_end=False)
        end = time_at(end_character, is_end=True)

        word_cursor = 0
        child_words: list[TranscriptWord] = []
        for word, length in zip(usable_words, word_lengths, strict=True):
            next_cursor = word_cursor + length
            if next_cursor > start_character and word_cursor < end_character:
                child_words.append(word)
            word_cursor = next_cursor
        result.append((start, end, tuple(child_words)))
    return result


def split_long_caption_segments(
    segments: list[TranscriptSegment],
    *,
    max_duration_seconds: float = MAX_DISPLAY_CAPTION_SECONDS,
    max_characters: int = MAX_DISPLAY_CAPTION_CHARACTERS,
) -> list[TranscriptSegment]:
    """按标点拆开过长字幕，并按字符比例分配原有时间范围。"""
    split_segments: list[TranscriptSegment] = []
    for segment in segments:
        text = normalize_text(segment.text)
        duration = segment.end - segment.start
        if duration <= max_duration_seconds and len(text) <= max_characters:
            split_segments.append(segment)
            continue

        clauses = [
            part
            for part in re.findall(r".*?[。！？!?；;，,、：:]|.+$", text)
            if part.strip()
        ]
        groups: list[str] = []
        if _chinese_character_count(text) > 0:
            # 中文逗号、顿号和句末标点本身就是稳定的阅读停顿，不再跨标点回拼。
            for clause in clauses:
                groups.extend(_split_long_clause(clause, max_characters))
        else:
            current = ""
            for clause in clauses:
                if current and len(current) + len(clause) > max_characters:
                    groups.append(current)
                    current = clause
                else:
                    current += clause
            if current:
                groups.append(current)
            if len(groups) == 1 and (
                duration > max_duration_seconds or len(text) > max_characters
            ):
                groups = _split_long_clause(text, max_characters)

        timings = _timing_for_groups(segment, groups)
        for group, (start, end, words) in zip(groups, timings, strict=True):
            split_segments.append(
                TranscriptSegment(
                    start=start,
                    end=end,
                    text=group,
                    avg_logprob=segment.avg_logprob,
                    no_speech_prob=segment.no_speech_prob,
                    compression_ratio=segment.compression_ratio,
                    min_word_probability=segment.min_word_probability,
                    low_confidence_word_ratio=segment.low_confidence_word_ratio,
                    words=words,
                )
            )
    return split_segments


def merge_readable_orphans(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """消除标点切分后残留的单词级字幕，优先并入紧邻的后句。"""
    working = list(segments)
    merged: list[TranscriptSegment] = []
    index = 0
    while index < len(working):
        current = working[index]

        # ASR 或 AI 校对可能把连接词、量词短语留在上一时间片末尾。
        # 保留原时间边界，把完整短语移入下一字幕即可恢复自然阅读顺序。
        if index + 1 < len(working) and working[index + 1].start - current.end <= 0.3:
            for phrase in CHINESE_TRAILING_BOUNDARY_PHRASES:
                if current.text.endswith(phrase) and len(current.text) > len(phrase):
                    following = working[index + 1]
                    current = TranscriptSegment(
                        start=current.start,
                        end=current.end,
                        text=current.text[: -len(phrase)].rstrip(),
                        avg_logprob=current.avg_logprob,
                        no_speech_prob=current.no_speech_prob,
                        compression_ratio=current.compression_ratio,
                        min_word_probability=current.min_word_probability,
                        low_confidence_word_ratio=current.low_confidence_word_ratio,
                        words=current.words,
                    )
                    working[index + 1] = TranscriptSegment(
                        start=following.start,
                        end=following.end,
                        text=f"{phrase}{following.text}",
                        avg_logprob=following.avg_logprob,
                        no_speech_prob=following.no_speech_prob,
                        compression_ratio=following.compression_ratio,
                        min_word_probability=following.min_word_probability,
                        low_confidence_word_ratio=following.low_confidence_word_ratio,
                        words=following.words,
                    )
                    break

        contains_chinese = _chinese_character_count(current.text) > 0
        is_orphan = (
            contains_chinese
            and (
                current.end - current.start < 1.5
                or _chinese_character_count(current.text) <= 6
            )
        )
        if (
            is_orphan
            and not _ends_complete_sentence(current.text)
            and index + 1 < len(working)
            and working[index + 1].start - current.end <= 0.3
            and not any(
                working[index + 1].text.endswith(phrase)
                for phrase in CHINESE_TRAILING_BOUNDARY_PHRASES
            )
            and len(current.text) + len(working[index + 1].text)
            <= MAX_DISPLAY_CAPTION_CHARACTERS
            and working[index + 1].end - current.start <= MAX_DISPLAY_CAPTION_SECONDS
        ):
            following = working[index + 1]
            merged.append(
                TranscriptSegment(
                    start=current.start,
                    end=following.end,
                    text=_join_continuation(current.text, following.text),
                    avg_logprob=min(current.avg_logprob, following.avg_logprob),
                    no_speech_prob=max(current.no_speech_prob, following.no_speech_prob),
                    compression_ratio=max(current.compression_ratio, following.compression_ratio),
                    min_word_probability=min(
                        current.min_word_probability,
                        following.min_word_probability,
                    ),
                    low_confidence_word_ratio=max(
                        current.low_confidence_word_ratio,
                        following.low_confidence_word_ratio,
                    ),
                    words=current.words + following.words,
                )
            )
            index += 2
            continue
        if (
            is_orphan
            and merged
            and current.start - merged[-1].end <= 0.3
            and len(merged[-1].text) + len(current.text)
            <= MAX_DISPLAY_CAPTION_CHARACTERS
            and current.end - merged[-1].start <= MAX_DISPLAY_CAPTION_SECONDS
        ):
            previous = merged.pop()
            merged.append(
                TranscriptSegment(
                    start=previous.start,
                    end=current.end,
                    text=_join_continuation(previous.text, current.text),
                    avg_logprob=min(previous.avg_logprob, current.avg_logprob),
                    no_speech_prob=max(previous.no_speech_prob, current.no_speech_prob),
                    compression_ratio=max(previous.compression_ratio, current.compression_ratio),
                    min_word_probability=min(
                        previous.min_word_probability,
                        current.min_word_probability,
                    ),
                    low_confidence_word_ratio=max(
                        previous.low_confidence_word_ratio,
                        current.low_confidence_word_ratio,
                    ),
                    words=previous.words + current.words,
                )
            )
        else:
            merged.append(current)
        index += 1
    return merged


def coalesce_caption_segments(
    segments: list[TranscriptSegment],
    *,
    max_duration_seconds: float = 8.0,
    max_characters: int = 42,
) -> list[TranscriptSegment]:
    """合并 ASR 过碎的句级时间片，不改写任何识别文字。"""
    merged: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None

    for segment in segments:
        text = normalize_text(segment.text)
        if not text:
            continue
        normalized = TranscriptSegment(
            start=segment.start,
            end=segment.end,
            text=text,
            avg_logprob=segment.avg_logprob,
            no_speech_prob=segment.no_speech_prob,
            compression_ratio=segment.compression_ratio,
            min_word_probability=segment.min_word_probability,
            low_confidence_word_ratio=segment.low_confidence_word_ratio,
            words=segment.words,
        )
        if current is None:
            current = normalized
            continue

        combined_text = _join_caption_text(current.text, normalized.text)
        should_break = (
            _ends_complete_sentence(current.text)
            or normalized.start - current.end > 1.2
            or normalized.end - current.start > max_duration_seconds
            or len(combined_text) > max_characters
        )
        if should_break:
            merged.append(current)
            current = normalized
            continue

        current = TranscriptSegment(
            start=current.start,
            end=normalized.end,
            text=_join_continuation(current.text, normalized.text),
            avg_logprob=min(current.avg_logprob, normalized.avg_logprob),
            no_speech_prob=max(current.no_speech_prob, normalized.no_speech_prob),
            compression_ratio=max(current.compression_ratio, normalized.compression_ratio),
            min_word_probability=min(current.min_word_probability, normalized.min_word_probability),
            low_confidence_word_ratio=max(
                current.low_confidence_word_ratio,
                normalized.low_confidence_word_ratio,
            ),
            words=current.words + normalized.words,
        )

    if current is not None:
        merged.append(current)
    return merged


def build_vtt(segments: list[TranscriptSegment]) -> str:
    cues = ["WEBVTT", "", "NOTE 由当前配置的纯音频 ASR 链路生成", ""]
    readable_segments = split_long_caption_segments(
        merge_readable_orphans(
            split_long_caption_segments(coalesce_caption_segments(segments))
        )
    )
    cue_number = 1
    for segment in readable_segments:
        display_text = normalize_text(DISPLAY_PUNCTUATION_PATTERN.sub("", segment.text))
        if not display_text:
            continue
        cues.extend(
            [
                str(cue_number),
                f"{vtt_timestamp(segment.start)} --> {vtt_timestamp(segment.end)}",
                display_text,
                "",
            ]
        )
        cue_number += 1
    return "\n".join(cues)


def build_analysis_result(
    *,
    video_id: str,
    duration_seconds: float,
    segments: list[TranscriptSegment],
    language: str,
    language_probability: float,
    model_name: str,
) -> AnalysisResult:
    if not segments:
        raise ValueError("没有识别到语音，请确认视频包含清晰音轨")

    transcript = normalize_text(" ".join(segment.text for segment in segments))
    confidence = min(0.99, max(0.55, language_probability))
    tags = extract_keywords(transcript)
    summary = select_summary(segments)
    return AnalysisResult(
        language=language,
        confidence=confidence,
        short_description=f"AI 已从音轨识别出 {len(segments)} 段字幕，并生成内容结构。",
        summary=summary,
        tags=tags,
        subtitles_vtt=build_vtt(segments),
        asr_model=f"faster-whisper {model_name} · CPU int8",
        chapters=build_chapters(video_id, duration_seconds, segments, confidence),
    )
