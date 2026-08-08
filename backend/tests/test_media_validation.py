import tempfile
import unittest
from pathlib import Path

import av
import numpy as np

from app.services.analysis_jobs import MediaAnalysisError, validate_audio_track


class MediaValidationTests(unittest.TestCase):
    def test_video_without_audio_track_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "video-only.mp4"
            container = av.open(str(path), "w")
            stream = container.add_stream("mpeg4", rate=10)
            stream.width = 160
            stream.height = 90
            stream.pix_fmt = "yuv420p"
            frame = av.VideoFrame.from_ndarray(
                np.zeros((90, 160, 3), dtype=np.uint8),
                format="rgb24",
            )
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            container.close()

            with self.assertRaises(MediaAnalysisError) as context:
                validate_audio_track(path)

            self.assertEqual(context.exception.code, "NO_AUDIO_TRACK")
            self.assertIn("没有可识别的音轨", context.exception.user_message)


if __name__ == "__main__":
    unittest.main()
