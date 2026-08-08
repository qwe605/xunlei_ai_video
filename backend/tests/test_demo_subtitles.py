import unittest
from pathlib import Path


class DemoSubtitleRegressionTests(unittest.TestCase):
    def test_dragon_egg_scene_keeps_words_and_audio_boundaries_together(self) -> None:
        """内置样例不得再次把“幸存”或“神器”拆到错误语音段。"""
        root = Path(__file__).resolve().parents[2]
        vtt = (root / "app/public/demo/parsevideo-chinese-demo.ai.zh-CN.vtt").read_text(
            encoding="utf-8"
        )

        self.assertIn("00:01:08.890 --> 00:01:10.030\n只剩一颗龙蛋幸存", vtt)
        self.assertIn("00:01:10.250 --> 00:01:11.450\n死后力量凝聚的遗蜕", vtt)
        self.assertIn("00:01:11.670 --> 00:01:13.210\n也成为了各族持有的神器", vtt)
        self.assertNotIn("各族持有的神\n", vtt)
        self.assertNotIn("\n器可", vtt)


if __name__ == "__main__":
    unittest.main()
