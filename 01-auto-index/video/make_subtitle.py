"""実測した音声の長さから、字幕ファイルを作る。

映像を見ずに字幕のタイミングを決められるのは、音声を先に作って
長さが確定しているからである。順序を逆にすると成立しない。

1 カットの音声を、文の区切りで分割して表示する。

使い方
    python3 make_subtitle.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMING = HERE / "timing.json"
OUT = HERE / "subtitle.srt"

#: 1 行に収める上限。これ以下なら折り返さない。
MAX_CHARS = 26

#: これを超えたら、読点が無くても 2 行にする。
HARD_MAX = 34

#: 文の区切り。
SENTENCE_RE = re.compile(r"[^。]*。|[^。]+$")


def to_timecode(seconds: float) -> str:
    """秒を SRT のタイムコードに変換する。

    Args:
        seconds: 開始からの秒数。

    Returns:
        `HH:MM:SS,mmm` 形式の文字列。
    """
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str) -> str:
    """必要な場合だけ 2 行に折り返す。

    日本語は単語の切れ目が文字に現れないため、文字数で機械的に割ると
    語の途中で切れる (実測: 「防ぐ種 / 類の問題」)。そこで

    - 読点があれば、中央にいちばん近い読点で切る
    - 読点が無ければ、HARD_MAX までは 1 行のまま置く
    - それも超える場合だけ中央で切る

    という順に判定する。行頭に句読点は置かない。

    Args:
        text: 1 文。

    Returns:
        必要なら改行を挟んだ文字列。
    """
    if len(text) <= MAX_CHARS:
        return text

    center = len(text) / 2
    commas = [i for i, ch in enumerate(text) if ch == "、"]

    if commas:
        cut = min(commas, key=lambda i: abs(i - center)) + 1
    elif len(text) <= HARD_MAX:
        return text
    else:
        cut = int(center)

    while cut < len(text) and text[cut] in "、。":
        cut += 1

    return text[:cut] + "\n" + text[cut:]


def main() -> None:
    """字幕ファイルを書き出す。"""
    data = json.loads(TIMING.read_text(encoding="utf-8"))

    blocks: list[str] = []
    index = 1
    offset = 0.0

    for cut in data["cuts"]:
        text = cut["text"]
        duration = float(cut["seconds"])
        sentences = [s.strip() for s in SENTENCE_RE.findall(text) if s.strip()]

        # 文字数の比で時間を割り振る。読み上げ速度が一定なので
        # これで実際の発話とほぼ一致する。
        total_chars = sum(len(s) for s in sentences)
        cursor = offset

        for sentence in sentences:
            span = duration * len(sentence) / total_chars
            blocks.append(
                f"{index}\n"
                f"{to_timecode(cursor)} --> {to_timecode(cursor + span)}\n"
                f"{wrap(sentence)}\n"
            )
            index += 1
            cursor += span

        offset += duration

    OUT.write_text("\n".join(blocks), encoding="utf-8")
    print(f"字幕 {index - 1} 件 / 全体 {offset:.2f} 秒")
    print(f"書き出し: {OUT}")


if __name__ == "__main__":
    main()
