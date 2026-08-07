"""場面データの構造と読み込み。

場面は JSON で書く。編ごとに違うのは JSON だけで、描く側の
コードは共通である。

場面の種類

    command  プロンプトを出し、コマンドを一文字ずつ打つ
    output   実行結果の行を出す
    clear    画面を消す。カットの切り替えに使う
    note     ターミナルを出さず、文言だけを見せる

JSON の例

    {
      "title": "gen",
      "scenes": [
        {"type": "clear"},
        {"type": "command", "text": "python3 build_index.py posts",
         "subtitle": "タグを基準に、記事を集計します。"},
        {"type": "output",
         "lines": [
           {"text": "  ○ automation        3 件", "color": "accent"},
           {"text": "  － ffmpeg            2 件", "color": "dim"}
         ],
         "subtitle": "automation が 3 件。", "hold": 3.5}
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_TYPES = {"command", "output", "clear", "note"}


@dataclass
class Row:
    """画面に出る 1 行。

    Attributes:
        text: 表示する文字列。プロンプトは含めない。
        color: 色の名前 (`theme.COLORS` のキー)。
        prompt: True ならプロンプトを頭に付ける。
    """

    text: str
    color: str = "fg"
    prompt: bool = False


@dataclass
class Scene:
    """1 つの場面。

    Attributes:
        kind: 場面の種類。`VALID_TYPES` のいずれか。
        text: `command` のとき打つ文字列。
        rows: `output` のとき出す行。
        subtitle: 行が出そろったあとに出す字幕。
        typing_subtitle: 打っている間に出す字幕。空なら `subtitle`。
        hold: 出そろってから次に進むまでの秒数。
        note: `note` のとき画面中央に出す文言。
    """

    kind: str
    text: str = ""
    rows: list[Row] = field(default_factory=list)
    subtitle: str = ""
    typing_subtitle: str = ""
    hold: float = 1.5
    note: str = ""


def load(path: Path) -> tuple[str, list[Scene]]:
    """場面データを読み込む。

    Args:
        path: JSON のパス。

    Returns:
        (窓のタイトルに出す名前, 場面の並び)。

    Raises:
        SystemExit: 形式が正しくないとき。
    """
    if not path.exists():
        raise SystemExit(f"場面データがありません: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    title = data.get("title", "zsh")
    scenes: list[Scene] = []

    for i, item in enumerate(data.get("scenes", []), 1):
        kind = item.get("type", "")
        if kind not in VALID_TYPES:
            raise SystemExit(f"{i} 番目: 知らない種類です: {kind!r}")

        rows = [
            Row(
                text=row.get("text", ""),
                color=row.get("color", "fg"),
                prompt=bool(row.get("prompt", False)),
            )
            for row in item.get("lines", [])
        ]

        if kind == "command" and not item.get("text"):
            raise SystemExit(f"{i} 番目: command には text が要ります")
        if kind == "note" and not item.get("note"):
            raise SystemExit(f"{i} 番目: note には note が要ります")

        scenes.append(
            Scene(
                kind=kind,
                text=item.get("text", ""),
                rows=rows,
                subtitle=item.get("subtitle", ""),
                typing_subtitle=item.get("typing_subtitle", ""),
                hold=float(item.get("hold", 1.5)),
                note=item.get("note", ""),
            )
        )

    if not scenes:
        raise SystemExit("場面が 1 つもありません")

    return title, scenes
