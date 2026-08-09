import re

from app.database.repositories.search_repository import SearchCorpusVideo, SearchRepository
from app.database.session import session_scope
from app.integrations.minimax import MinimaxSummaryError, request_video_answer
from app.schemas import SearchCitation, VideoQuestionRequest, VideoQuestionResponse


_SPLIT_PATTERN = re.compile(r"[\s，。、“”‘’：；！？，./_\-[\]()（）]+")
_FILLERS = re.compile(r"(有没有|是否|能不能|能否|请问|这个|视频|里面|后面|前面|讲|说|介绍|一下)")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("的", "").lower()


def _question_terms(question: str) -> list[str]:
    cleaned = _FILLERS.sub(" ", question.lower())
    terms = [
        term.strip()
        for term in _SPLIT_PATTERN.split(cleaned)
        if len(term.strip()) > 1 or re.match(r"^[a-z0-9]+$", term.strip())
    ]
    return list(dict.fromkeys(terms))


class QuestionService:
    """“问视频”业务层：先检索当前视频证据，再生成答案；没有证据时必须拒答。"""

    def answer_video_question(
        self,
        *,
        video_id: str,
        payload: VideoQuestionRequest,
        owner_id: str = "demo-local",
    ) -> VideoQuestionResponse:
        with session_scope() as session:
            item = SearchRepository(session).get_searchable_video(video_id, owner_id)
        if item is None:
            raise LookupError("视频不存在或无权访问")

        citations = self._retrieve_video_citations(item, payload.question, payload.limit)
        if not citations:
            return VideoQuestionResponse(
                video_id=video_id,
                question=payload.question,
                status="no_evidence",
            )

        try:
            answer = request_video_answer(payload.question, citations)
            cited = [citation for citation in citations if citation.id in set(answer.citation_ids)]
            return VideoQuestionResponse(
                video_id=video_id,
                question=payload.question,
                status="answered",
                answer=answer.answer,
                confidence=max((citation.confidence for citation in cited), default=0.55),
                citations=cited[:3],
            )
        except MinimaxSummaryError:
            # 本地无 Key 或网络不可用时只基于证据摘句，不使用常识补答，保证演示链路可用。
            primary = citations[0]
            return VideoQuestionResponse(
                video_id=video_id,
                question=payload.question,
                status="answered",
                answer=f"根据当前视频证据，{primary.text}",
                confidence=primary.confidence,
                citations=[primary],
            )

    def _retrieve_video_citations(
        self,
        item: SearchCorpusVideo,
        question: str,
        limit: int,
    ) -> list[SearchCitation]:
        video = item.record
        terms = _question_terms(question)
        if not terms:
            return []

        candidates: list[tuple[float, SearchCitation]] = []
        for chapter in video.chapters:
            text = f"{chapter.title}：{chapter.summary}"
            score = self._score_text(text, terms) * 3
            if score <= 0:
                continue
            candidates.append(
                (
                    score,
                    SearchCitation(
                        id=f"question-chapter-{video.id}-{chapter.id}",
                        video_id=video.id,
                        start_seconds=chapter.start_seconds,
                        end_seconds=max(chapter.end_seconds, chapter.start_seconds + 0.5),
                        text=text,
                        source_type="chapter",
                        confidence=min(0.98, chapter.confidence * min(1, score / 5)),
                    ),
                )
            )

        for segment in video.transcript_segments:
            score = self._score_text(segment.text, terms)
            if score <= 0:
                continue
            candidates.append(
                (
                    score,
                    SearchCitation(
                        id=f"question-subtitle-{video.id}-{segment.segment_index}",
                        video_id=video.id,
                        start_seconds=segment.start_seconds,
                        end_seconds=max(segment.end_seconds, segment.start_seconds + 0.5),
                        text=segment.text[:500],
                        source_type="subtitle",
                        confidence=min(0.96, max(0.4, video.confidence * min(1, score / 4))),
                    ),
                )
            )

        return [
            citation
            for _, citation in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]
        ]

    def _score_text(self, text: str, terms: list[str]) -> float:
        normalized = _normalize_text(text)
        score = 0.0
        for term in terms:
            normalized_term = _normalize_text(term)
            if normalized_term and normalized_term in normalized:
                score += 1.5 if len(normalized_term) <= 2 else 2.2
        if score > 0 and len(text) <= 80:
            score += 0.4
        return score
