import unittest

from app.services.content_analysis import TranscriptSegment
from app.services.subtitle_review import select_suspicious_segments


class SubtitleReviewTests(unittest.TestCase):
    def test_selects_only_low_confidence_segments(self) -> None:
        segments = [
            TranscriptSegment(0, 2, "clear speech", avg_logprob=-0.2),
            TranscriptSegment(2, 4, "walker aar", avg_logprob=-1.1),
            TranscriptSegment(4, 6, "normal again", avg_logprob=-0.3),
        ]

        self.assertEqual(select_suspicious_segments(segments), [1])

    def test_selects_segment_with_one_uncertain_word(self) -> None:
        segments = [
            TranscriptSegment(
                0,
                4,
                "使用 MiniMax M3 进行整理",
                avg_logprob=-0.2,
                min_word_probability=0.18,
                low_confidence_word_ratio=0.1,
            )
        ]

        self.assertEqual(select_suspicious_segments(segments), [0])

    def test_can_review_all_chinese_segments_in_the_same_ai_request(self) -> None:
        segments = [
            TranscriptSegment(0, 3, "这个世界居住着人类。"),
            TranscriptSegment(3, 6, "四只烛龙从天外降临。"),
        ]

        self.assertEqual(select_suspicious_segments(segments, review_all=True), [0, 1])

if __name__ == "__main__":
    unittest.main()
