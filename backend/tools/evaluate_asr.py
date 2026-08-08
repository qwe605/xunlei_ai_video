"""用人工字幕或内嵌字幕真值评估纯音频 ASR 的字错率与专名召回。"""

import argparse
import json
import re
from pathlib import Path

from rapidfuzz.distance import Levenshtein


def transcript(path: Path) -> str:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "".join(
        line
        for line in lines
        if line
        and line != "WEBVTT"
        and not line.startswith("NOTE ")
        and "-->" not in line
        and not line.isdigit()
    )
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text).lower()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("hypothesis", type=Path)
    parser.add_argument("--terms", default="")
    parser.add_argument("--terms-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reference = transcript(args.reference)
    hypothesis = transcript(args.hypothesis)
    terms = [value.strip() for value in args.terms.split(",") if value.strip()]
    if args.terms_file:
        terms.extend(
            value.strip()
            for value in args.terms_file.read_text(encoding="utf-8").splitlines()
            if value.strip()
        )
    result = {
        "referenceCharacters": len(reference),
        "hypothesisCharacters": len(hypothesis),
        "characterErrorRate": round(
            Levenshtein.distance(reference, hypothesis) / max(1, len(reference)),
            4,
        ),
        "termRecall": {
            term: term.lower() in hypothesis
            for term in terms
        },
    }
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
