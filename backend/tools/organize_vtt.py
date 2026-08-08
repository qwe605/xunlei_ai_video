"""将离线 ASR 字幕交给 MiniMax 整理为摘要、标签和章节。"""

import argparse
import json
import re
import sys
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3}) --> "
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})\r?\n"
    r"(?P<text>.*?)(?=\r?\n\r?\n|\Z)",
    re.DOTALL,
)


def seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("subtitles", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--asr-model", required=True)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--review-all", action="store_true")
    parser.add_argument("--subtitles-output", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.content_analysis import TranscriptSegment, prepare_segments_for_review
    from app.integrations.minimax import build_minimax_result

    content = args.subtitles.read_text(encoding="utf-8")
    segments = [
        TranscriptSegment(
            start=seconds(match.group("start")),
            end=seconds(match.group("end")),
            text=" ".join(match.group("text").splitlines()).strip(),
        )
        for match in TIMESTAMP_PATTERN.finditer(content)
        if match.group("text").strip()
    ]
    if not segments:
        raise ValueError("字幕文件中没有可整理的时间片段")

    segments = prepare_segments_for_review(segments)
    duration = args.duration or segments[-1].end
    result = build_minimax_result(
        video_id=args.video_id,
        duration_seconds=duration,
        segments=segments,
        language="中文（简体）",
        language_probability=0.95,
        asr_model=args.asr_model,
        suspicious_indexes=set(range(len(segments))) if args.review_all else set(),
    )
    args.output.write_text(
        json.dumps(
            {
                "durationSeconds": duration,
                **result.model_dump(by_alias=True),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if args.subtitles_output:
        args.subtitles_output.write_text(result.subtitles_vtt, encoding="utf-8")
    print(f"完成：{len(segments)} 段字幕，{len(result.chapters)} 个章节")


if __name__ == "__main__":
    main()
