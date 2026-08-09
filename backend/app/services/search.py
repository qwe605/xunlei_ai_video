import math
import re
from collections import Counter
from dataclasses import dataclass

from app.database.repositories.search_repository import SearchCorpusVideo, SearchRepository
from app.database.session import session_scope
from app.schemas import SearchCitation, SearchRequest, SearchResponse, SearchResultItem


_SPLIT_PATTERN = re.compile(r"[\s，。、“”‘’：；！？，./_\-[\]()（）]+")
_FILLERS = re.compile(r"(找我保存的|找一下|找|讲|关于|那个|这部|视频|片段|内容|一下)")


@dataclass(frozen=True)
class _ScoredSearchResult:
    video_id: str
    score: float
    reasons: list[str]
    citations: list[SearchCitation]


def _normalize_text(value: str) -> str:
    # 中文搜索对空格和助词不敏感；保留英文字母数字，方便搜模型名、文件名和专有名词。
    return re.sub(r"\s+", "", value).replace("的", "").lower()


def _query_terms(query: str) -> list[str]:
    cleaned = _FILLERS.sub(" ", query.lower())
    terms = [
        term.strip()
        for term in _SPLIT_PATTERN.split(cleaned)
        if len(term.strip()) > 1 or re.match(r"^[a-z0-9]+$", term.strip())
    ]
    # 去重但保留顺序，便于解释命中的关键词。
    return list(dict.fromkeys(terms))


def _term_frequency(text: str, terms: list[str]) -> float:
    normalized = _normalize_text(text)
    return sum(normalized.count(_normalize_text(term)) for term in terms)


def _confidence_label(score: float) -> str:
    if score >= 9:
        return "高"
    if score >= 4:
        return "中"
    return "低"


class SearchService:
    """自然语言搜索业务层；当前先做可解释混合检索，后续可在此接入 embedding 召回。"""

    def search(self, payload: SearchRequest, owner_id: str = "demo-local") -> SearchResponse:
        query = payload.query.strip()
        if not query:
            return SearchResponse(query=payload.query, mode=payload.mode, total=0, results=[])

        terms = _query_terms(query)
        with session_scope() as session:
            corpus = SearchRepository(session).list_searchable_videos(owner_id)

        scored = [
            self._score_filename(item, query, terms)
            if payload.mode == "filename"
            else self._score_hybrid(item, query, terms)
            for item in corpus
        ]
        results = [
            SearchResultItem(
                video_id=item.video_id,
                score=round(item.score, 3),
                confidence_label=_confidence_label(item.score),
                match_reasons=item.reasons[:5],
                citations=item.citations[:3],
            )
            for item in sorted(
                (item for item in scored if item.score > 0),
                key=lambda item: item.score,
                reverse=True,
            )[: payload.limit]
        ]
        return SearchResponse(
            query=query,
            mode=payload.mode,
            total=len(results),
            results=results,
        )

    def _score_filename(
        self,
        item: SearchCorpusVideo,
        query: str,
        terms: list[str],
    ) -> _ScoredSearchResult:
        video = item.record
        title = _normalize_text(video.title)
        filename = _normalize_text(video.original_filename)
        normalized_query = _normalize_text(query)
        score = 0.0
        reasons: list[str] = []

        if normalized_query and normalized_query in title:
            score += 12
            reasons.append("展示名称直接命中")
        if normalized_query and normalized_query in filename:
            score += 10
            reasons.append("原文件名直接命中")
        term_hits = sum(1 for term in terms if _normalize_text(term) in title or _normalize_text(term) in filename)
        if term_hits:
            score += term_hits * 2
            reasons.append(f"文件信息命中 {term_hits} 个关键词")

        citation = SearchCitation(
            id=f"filename-{video.id}",
            video_id=video.id,
            start_seconds=0,
            end_seconds=min(max(video.duration_seconds, 1), 8),
            text=f"{video.title} / {video.original_filename}",
            source_type="filename",
            confidence=min(0.98, score / 14) if score else 0.1,
        )
        return _ScoredSearchResult(video.id, score, reasons, [citation] if score else [])

    def _score_hybrid(
        self,
        item: SearchCorpusVideo,
        query: str,
        terms: list[str],
    ) -> _ScoredSearchResult:
        video = item.record
        if video.index_status not in {"ready", "processing", "pending"}:
            return _ScoredSearchResult(video.id, 0, [], [])

        metadata_text = " ".join(
            [video.title, video.original_filename, video.short_description, video.summary]
            + [tag.name for tag in video.tags]
        )
        chapter_candidates = [
            (
                chapter.start_seconds,
                chapter.end_seconds,
                f"{chapter.title}：{chapter.summary}",
                _term_frequency(f"{chapter.title} {chapter.summary}", terms) * 3.2,
                "chapter",
                chapter.confidence,
            )
            for chapter in video.chapters
        ]
        subtitle_candidates = [
            (
                segment.start_seconds,
                segment.end_seconds,
                segment.text,
                self._subtitle_score(segment.text, segment.normalized_text, query, terms),
                "subtitle",
                min(0.96, video.confidence),
            )
            for segment in video.transcript_segments
        ]

        metadata_score = _term_frequency(metadata_text, terms) * 1.8
        tag_hits = [tag.name for tag in video.tags if any(_normalize_text(term) in _normalize_text(tag.name) for term in terms)]
        citations = self._best_citations(video.id, chapter_candidates + subtitle_candidates)
        evidence_score = sum((citation.confidence * 2.2) for citation in citations)

        # RRF 思想在这里体现为“元数据召回 + 字幕片段召回 + 章节召回”的稳定融合。
        score = metadata_score + evidence_score + (video.confidence * 1.2)
        reasons: list[str] = []
        if tag_hits:
            reasons.append(f"标签命中：{'、'.join(tag_hits[:3])}")
        elif metadata_score > 0:
            reasons.append("标题、摘要或文件信息与描述相关")
        if citations:
            first = citations[0]
            minutes = math.floor(first.start_seconds / 60)
            seconds = math.floor(first.start_seconds % 60)
            reasons.append(f"相关证据位于 {minutes:02d}:{seconds:02d}")
        if not reasons and _normalize_text(query) in _normalize_text(metadata_text):
            reasons.append("完整描述在视频信息中出现")
            score += 3

        return _ScoredSearchResult(video.id, score, reasons, citations)

    def _subtitle_score(
        self,
        text: str,
        normalized_text: str,
        query: str,
        terms: list[str],
    ) -> float:
        normalized_query = _normalize_text(query)
        score = 0.0
        if normalized_query and normalized_query in normalized_text:
            score += 6
        term_counts = Counter(_normalize_text(term) for term in terms)
        for term, weight in term_counts.items():
            if term and term in normalized_text:
                score += 2.6 * weight
        # 较短字幕命中通常比长段落更聚焦，给用户跳转时也更容易核验。
        if score > 0 and len(text) <= 60:
            score += 0.6
        return score

    def _best_citations(
        self,
        video_id: str,
        candidates: list[tuple[float, float, str, float, str, float]],
    ) -> list[SearchCitation]:
        citations: list[SearchCitation] = []
        for index, (start, end, text, score, source_type, base_confidence) in enumerate(
            sorted(candidates, key=lambda item: item[3], reverse=True)
        ):
            if score <= 0:
                continue
            citations.append(
                SearchCitation(
                    id=f"{source_type}-{video_id}-{index}-{int(start * 1000)}",
                    video_id=video_id,
                    start_seconds=start,
                    end_seconds=max(end, start + 0.5),
                    text=text[:500],
                    source_type=source_type,
                    confidence=min(0.99, max(0.35, base_confidence * min(1.0, score / 8))),
                )
            )
            if len(citations) >= 3:
                break
        return citations
