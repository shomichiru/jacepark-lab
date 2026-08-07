"""記事のメタ情報から、まとめページを自動生成する。

各記事が自分の所属を宣言し、本スクリプトがそれを集めて一覧を作る。
まとめページを人が書かないので、記事を直してまとめを直し忘れる、という
事故が起きなくなる。

記事側の書き方
    HTML の先頭にメタブロックを置き、`tags:` に所属を書く。

        <!--META
        title: 記事のタイトル
        slug: article-slug
        tags: [python, automation]
        note: 一覧に出す一行
        -->

使い方
    python3 build_index.py posts        集計だけ表示
    python3 build_index.py posts --build  3 件以上のタグの一覧を生成

終了コード
    0 = 正常 / 2 = 引数エラー
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: 生成した一覧の置き場。
OUTPUT_DIR = Path("output")

#: 一覧を作る下限。これ未満のタグはページを作らない。
#:
#: 1~2 件のページを量産すると、中身の薄いページが並ぶだけになる。
MIN_ENTRIES = 3

#: メタブロック。
META_BLOCK_RE = re.compile(r"<!--META\s*(.*?)-->", re.DOTALL)

#: メタブロックの 1 行。
META_KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")


def parse_meta(text: str) -> dict[str, str]:
    """メタブロックを辞書で返す。

    Args:
        text: 記事ファイルの全文。

    Returns:
        キーと値の辞書。ブロックが無ければ空の辞書。
    """
    match = META_BLOCK_RE.search(text)
    if not match:
        return {}

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        kv = META_KV_RE.match(line.strip())
        if kv:
            meta[kv.group(1)] = kv.group(2).strip()
    return meta


def parse_list(value: str) -> list[str]:
    """`[a, b, c]` 形式を配列で返す。

    Args:
        value: メタブロックの値。

    Returns:
        要素の配列。空なら空配列。
    """
    stripped = value.strip().strip("[]").strip()
    if not stripped:
        return []
    return [item.strip() for item in stripped.split(",") if item.strip()]


def collect(posts_dir: Path) -> dict[str, list[dict[str, str]]]:
    """記事を走査してタグごとにまとめる。

    Args:
        posts_dir: 記事ファイルの置き場。

    Returns:
        `{タグ: [記事情報, ...]}`。
    """
    result: dict[str, list[dict[str, str]]] = {}

    for path in sorted(posts_dir.glob("*.html")):
        meta = parse_meta(path.read_text(encoding="utf-8"))
        if not meta.get("title") or not meta.get("slug"):
            continue

        entry = {
            "title": meta["title"],
            "slug": meta["slug"],
            "note": meta.get("note", ""),
        }
        for tag in parse_list(meta.get("tags", "")):
            result.setdefault(tag, []).append(entry)

    return result


def build_html(tag: str, entries: list[dict[str, str]]) -> str:
    """まとめページの HTML を組み立てる。

    説明文は置かない。見出しと表だけで成立させる。

    Args:
        tag: タグ名。
        entries: そのタグの記事一覧。

    Returns:
        HTML 全文。
    """
    rows = "\n".join(
        f'    <tr><td><a href="/{item["slug"]}/">{item["title"]}</a></td>'
        f'<td>{item["note"] or "—"}</td></tr>'
        for item in sorted(entries, key=lambda e: e["title"])
    )

    return f"""<h1>{tag} の記事</h1>
<table>
  <thead>
    <tr><th>記事</th><th>ひとこと</th></tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>
"""


def main(argv: list[str]) -> int:
    """コマンドラインの入口。

    Args:
        argv: 引数（1 つ目 = 記事ディレクトリ、`--build` で生成）。

    Returns:
        終了コード。
    """
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}

    if len(args) != 1 or flags - {"--build"}:
        print("使い方: python3 build_index.py <記事ディレクトリ> [--build]")
        return 2

    posts_dir = Path(args[0])
    if not posts_dir.is_dir():
        print(f"ディレクトリがありません: {posts_dir}")
        return 2

    collected = collect(posts_dir)
    if not collected:
        print("タグを持つ記事がありません。")
        return 0

    buildable = []
    for tag, entries in sorted(collected.items()):
        count = len(entries)
        mark = "○" if count >= MIN_ENTRIES else "－"
        print(f"  {mark} {tag:<16} {count:>2} 件")
        if count >= MIN_ENTRIES:
            buildable.append((tag, entries))

    if "--build" not in flags:
        print()
        print("生成するには --build を付けます。")
        return 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    print()
    for tag, entries in buildable:
        out = OUTPUT_DIR / f"{tag}.html"
        out.write_text(build_html(tag, entries), encoding="utf-8")
        print(f"生成: {out} ({len(entries)} 件)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
