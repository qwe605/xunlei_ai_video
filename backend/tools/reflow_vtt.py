"""合并 WebVTT 中相邻的碎片字幕，不修改识别文本。"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.content_analysis import TranscriptSegment, build_vtt


TIMING_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)


def seconds(value: str) -> float:
    hours, minutes, remainder = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(remainder)


def parse_vtt(path: Path) -> list[TranscriptSegment]:
    blocks = re.split(r"\r?\n\r?\n", path.read_text(encoding="utf-8-sig").strip())
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next(
            (index for index, line in enumerate(lines) if TIMING_PATTERN.fullmatch(line)),
            None,
        )
        if timing_index is None:
            continue
        match = TIMING_PATTERN.fullmatch(lines[timing_index])
        if match is None:
            continue
        text = "".join(lines[timing_index + 1 :])
        if text:
            segments.append(
                TranscriptSegment(
                    start=seconds(match.group("start")),
                    end=seconds(match.group("end")),
                    text=text,
                )
            )
    return segments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--analysis-json",
        type=Path,
        help="同时更新预计算分析 JSON 中的 subtitlesVtt 字段",
    )
    args = parser.parse_args()
    subtitles_vtt = build_vtt(parse_vtt(args.input))
    args.output.write_text(subtitles_vtt, encoding="utf-8")
    if args.analysis_json:
        analysis = json.loads(args.analysis_json.read_text(encoding="utf-8"))
        analysis["subtitlesVtt"] = subtitles_vtt
        args.analysis_json.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
