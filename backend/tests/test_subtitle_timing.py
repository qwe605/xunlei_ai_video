import unittest

from app.services.content_analysis import TranscriptSegment
from app.services.subtitle_alignment import align_subtitle_timing, render_aligned_vtt


class SubtitleTimingAlignmentTests(unittest.TestCase):
    def test_reference_pause_delays_following_caption(self) -> None:
        ai_segments = [
            TranscriptSegment(113.896, 116.697, "那么所有士兵都会获得额外的两千点血量"),
            TranscriptSegment(116.697, 117.581, "攻击力同理"),
            TranscriptSegment(117.581, 119.940, "三月初超凡者小队抵达战斗地点"),
        ]
        reference_segments = [
            TranscriptSegment(115.5, 117.0, "那么所有士兵都会获得"),
            TranscriptSegment(117.0, 119.5, "额外的2000点血量，攻击力同理"),
            TranscriptSegment(119.5, 120.0, "3月初"),
            TranscriptSegment(120.0, 122.0, "超凡者小队抵达战斗地点"),
        ]

        result = align_subtitle_timing(ai_segments, reference_segments)

        self.assertGreaterEqual(result.segments[2].start, 119.45)
        self.assertLessEqual(result.segments[2].start, 120.05)
        self.assertEqual(result.segments[2].text, ai_segments[2].text)

    def test_overlapping_matches_are_resolved_monotonically(self) -> None:
        ai_segments = [
            TranscriptSegment(0.0, 2.0, "额外的两千点血量"),
            TranscriptSegment(2.0, 3.0, "攻击力同理"),
        ]
        reference_segments = [
            TranscriptSegment(1.0, 4.0, "额外的2000点血量，攻击力同理"),
        ]

        result = align_subtitle_timing(ai_segments, reference_segments)

        self.assertLessEqual(result.segments[0].end, result.segments[1].start)
        self.assertTrue(all(item.end > item.start for item in result.segments))

    def test_low_confidence_caption_uses_neighboring_anchor_shift(self) -> None:
        ai_segments = [
            TranscriptSegment(10.0, 12.0, "第一句可靠字幕"),
            TranscriptSegment(12.0, 14.0, "无法匹配的内容"),
            TranscriptSegment(14.0, 16.0, "第三句可靠字幕"),
        ]
        reference_segments = [
            TranscriptSegment(12.0, 14.0, "第一句可靠字幕"),
            TranscriptSegment(16.0, 18.0, "第三句可靠字幕"),
        ]

        result = align_subtitle_timing(ai_segments, reference_segments)

        self.assertAlmostEqual(result.segments[1].start, 14.0, delta=0.2)
        self.assertIn(1, result.low_confidence_indexes)

    def test_rendering_does_not_merge_calibrated_captions(self) -> None:
        segments = [
            TranscriptSegment(117.0, 119.5, "攻击力同理"),
            TranscriptSegment(120.0, 122.0, "三月初超凡者小队抵达战斗地点"),
        ]

        content = render_aligned_vtt(segments)

        self.assertEqual(content.count(" --> "), 2)
        self.assertIn("00:01:57.000 --> 00:01:59.500\n攻击力同理", content)
        self.assertIn("00:02:00.000 --> 00:02:02.000\n三月初", content)


if __name__ == "__main__":
    unittest.main()
