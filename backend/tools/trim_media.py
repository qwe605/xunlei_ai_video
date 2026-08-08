"""按有效内容结束时间无损裁剪媒体，移除下载文件中的异常静态尾段。"""

import argparse
from pathlib import Path

import av


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--end", type=float, required=True)
    args = parser.parse_args()

    with av.open(str(args.source), metadata_errors="ignore") as source:
        with av.open(str(args.output), mode="w") as output:
            streams = {
                stream.index: output.add_stream_from_template(stream)
                for stream in source.streams
                if stream.type in {"audio", "video"}
            }
            for packet in source.demux():
                if packet.stream.index not in streams or packet.dts is None:
                    continue
                timestamp = float(packet.dts * packet.time_base)
                if timestamp > args.end:
                    continue
                packet.stream = streams[packet.stream.index]
                output.mux(packet)

    print(f"已裁剪至 {args.end:.2f} 秒：{args.output}")


if __name__ == "__main__":
    main()
