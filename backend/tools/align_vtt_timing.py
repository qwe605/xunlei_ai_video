"""依据 SRT/VTT 标准答案校准 AI VTT 时间轴，并输出可审计报告。"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.content_analysis import TranscriptSegment
from app.services.subtitle_alignment import align_subtitle_timing, render_aligned_vtt


TIMING_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def seconds(value: str) -> float:
    hours, minutes, remainder = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(remainder)


def parse_timed_text(path: Path) -> list[TranscriptSegment]:
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig").strip())
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
        text = "".join(lines[timing_index + 1 :])
        if match is not None and text:
            segments.append(
                TranscriptSegment(
                    start=seconds(match.group("start")),
                    end=seconds(match.group("end")),
                    text=text,
                )
            )
    return segments


def clip_reference(
    segments: list[TranscriptSegment],
    source_offset: float,
    duration: float,
) -> list[TranscriptSegment]:
    end = source_offset + duration
    return [
        TranscriptSegment(
            start=max(0.0, item.start - source_offset),
            end=min(duration, item.end - source_offset),
            text=item.text,
        )
        for item in segments
        if item.end > source_offset and item.start < end
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="待校准的 AI VTT")
    parser.add_argument("reference", type=Path, help="仅用于时间校准的 SRT/VTT")
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-offset", type=float, default=0.0)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--analysis-json", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    original = parse_timed_text(args.input)
    reference = clip_reference(
        parse_timed_text(args.reference), args.source_offset, args.duration
    )
    result = align_subtitle_timing(original, reference)
    subtitles_vtt = render_aligned_vtt(result.segments)
    args.output.write_text(subtitles_vtt, encoding="utf-8")

    if args.analysis_json:
        analysis = json.loads(args.analysis_json.read_text(encoding="utf-8"))
        analysis["subtitlesVtt"] = subtitles_vtt
        args.analysis_json.write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    corrections = [
        abs((after.start + after.end - before.start - before.end) / 2)
        for before, after in zip(original, result.segments, strict=True)
    ]
    report = {
        "captionCount": len(original),
        "anchorCount": len(original) - len(result.low_confidence_indexes),
        "lowConfidenceIndexes": result.low_confidence_indexes,
        "averageCenterCorrectionSeconds": round(sum(corrections) / max(1, len(corrections)), 3),
        "maximumCenterCorrectionSeconds": round(max(corrections, default=0.0), 3),
    }
    if args.report:
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
