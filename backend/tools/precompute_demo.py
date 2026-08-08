"""把真实视频离线整理为前端可直接加载的字幕、封面和结构化 AI 结果。"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--engine", choices=("funasr", "faster-whisper"), default="funasr")
    parser.add_argument("--copy-media", action="store_true")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--skip-poster", action="store_true")
    return parser.parse_args()


def inspect_video(source: Path) -> tuple[float, int, int, object]:
    import av

    with av.open(str(source), metadata_errors="ignore") as container:
        video = container.streams.video[0]
        duration = float(container.duration / av.time_base)
        target = int(duration * 0.08 * av.time_base)
        container.seek(target)
        frame = next(container.decode(video))
        return duration, int(video.width), int(video.height), frame


def main() -> None:
    args = parse_args()
    os.environ["XUNLEI_ASR_ENGINE"] = args.engine

    # 脚本位于 backend/tools，需要先把 backend 加入模块搜索路径。
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))

    from app.integrations.asr import create_transcriber
    from app.integrations.minimax import build_minimax_result
    from app.services.content_analysis import prepare_segments_for_review
    from app.services.subtitle_review import select_suspicious_segments

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.duration and args.width and args.height:
        duration, width, height = args.duration, args.width, args.height
        frame = None
    else:
        duration, width, height, frame = inspect_video(args.source)
    segments, info = create_transcriber().transcribe(args.source, duration)
    review_segments = prepare_segments_for_review(segments)
    suspicious = set(
        select_suspicious_segments(
            review_segments,
            limit=64,
            review_all=info.language.startswith("中文"),
        )
    )
    result = build_minimax_result(
        video_id=args.video_id,
        duration_seconds=duration,
        segments=review_segments,
        language=info.language,
        language_probability=info.language_probability,
        asr_model=info.model_label,
        suspicious_indexes=suspicious,
    )

    stem = args.video_id
    (args.output_dir / f"{stem}.analysis.json").write_text(
        json.dumps(
            {
                "durationSeconds": duration,
                "width": width,
                "height": height,
                **result.model_dump(by_alias=True),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output_dir / f"{stem}.ai.zh-CN.vtt").write_text(
        result.subtitles_vtt,
        encoding="utf-8",
    )
    if not args.skip_poster:
        if frame is None:
            _, _, _, frame = inspect_video(args.source)
        frame.to_image().save(args.output_dir / f"{stem}-poster.jpg", quality=88)
    if args.copy_media:
        shutil.copy2(args.source, args.output_dir / f"{stem}{args.source.suffix.lower()}")

    print(
        f"完成：{len(review_segments)} 段字幕，{len(result.chapters)} 个章节，"
        f"{duration:.1f} 秒，{width}x{height}"
    )


if __name__ == "__main__":
    main()
