"""用 faster-whisper 离线生成可复用的 WebVTT 字幕。"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from faster_whisper import WhisperModel

    from app.services.content_analysis import TranscriptSegment, build_vtt
    from app.services.text_normalization import to_simplified_chinese

    compute_type = "float16" if args.device == "cuda" else "int8"
    model = WhisperModel(args.model, device=args.device, compute_type=compute_type)
    raw, info = model.transcribe(
        str(args.source),
        language=args.language,
        task="transcribe",
        initial_prompt="这是面向中国大陆用户的视频字幕，包含游戏、互联网和软件专有名词。",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True,
        word_timestamps=True,
    )
    segments = [
        TranscriptSegment(
            float(segment.start),
            float(segment.end),
            to_simplified_chinese(segment.text.strip()),
        )
        for segment in raw
        if segment.text.strip()
    ]
    args.output.write_text(build_vtt(segments), encoding="utf-8")
    print(f"完成：{len(segments)} 段字幕，语言 {info.language}")


if __name__ == "__main__":
    main()
