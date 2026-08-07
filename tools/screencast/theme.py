"""画面の見た目を決める値をまとめる。

編ごとに変えるものではない。ここを直せば全ての動画に反映される。

数値は実際の macOS ターミナル (1330x740 の窓) を計測して決めた
(2026-08-07)。窓の桁数・行数はここから計算するので、飾りではなく
実際に入る数と一致する。
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

#: 出力の解像度と frame rate。
WIDTH, HEIGHT = 1920, 1080
FPS = 30

#: 配色。ターミナル本体は暗色、窓枠のタイトルバーは明色。
DESKTOP = (12, 13, 16)
BG = (24, 26, 30)
FG = (222, 226, 232)
DIM = (120, 128, 140)
ACCENT = (126, 200, 120)
MARK = (240, 200, 90)
USER = (186, 140, 232)
PATH = (110, 190, 220)
TITLEBAR = (236, 236, 238)
TITLEBAR_LINE = (206, 206, 210)
TITLE_FG = (48, 50, 54)
LIGHTS = [(255, 95, 87), (255, 189, 46), (40, 201, 64)]

#: 色の名前。場面データから文字列で指定できるようにする。
COLORS = {
    "fg": FG,
    "dim": DIM,
    "accent": ACCENT,
    "mark": MARK,
    "user": USER,
    "path": PATH,
}

#: 窓のレイアウト。
WIN_W = 1120
WIN_H = 624
WIN_MARGIN_X = (WIDTH - WIN_W) // 2
WIN_TOP = 105
TITLEBAR_H = 44
WIN_RADIUS = 14
LIGHT_R = 7
LIGHT_GAP = 24
LIGHT_X = 26

#: 本文のレイアウト。
PAD_X, PAD_Y = 18, 16
LINE_H = 26
MONO_SIZE = 20

#: 字幕のレイアウト。最下端には貼り付けない。YouTube が再生中に
#: 下端へコントロールバーを重ねるためである。
SUB_SIZE = 44
SUB_BOTTOM_RATIO = 0.12
SUB_PAD = 26
SUB_BG = (0, 0, 0)
SUB_ALPHA = 170
SUB_RADIUS = 10

#: プロンプト。絵文字は文字として描けないので画像で貼る。
PROMPT_HEAD = "try"
PROMPT_EMOJI = "\N{DOG FACE}"
PROMPT_HEAD_TAIL = "everything"
PROMPT_FALLBACK = "try@everything"

#: タイピングの速さ (1 秒あたりの文字数)。
TYPE_CPS = 6.5

#: 字幕を先に出してから手を動かし始めるまでの秒数。
#: 人は「〜してみます」と言ってから打ち始める。字幕とタイピングを
#: 交互に止めて見せると、段取りが一つずつ切れて機械的になる。
SUB_LEAD = 0.5

#: コマンドを打ち終えてから出力が出るまでの秒数。実行そのものは
#: 一瞬なので、ここで待たせない。
RUN_DELAY = 0.25

#: 最後の場面のあとに置く余韻の秒数。喋り終わった直後に切れると
#: 追い立てられている印象になる。読み終える時間も要る。
OUTRO = 3.0

#: 字幕を読むのに要る時間。日本語は 1 秒あたり 6 文字ほどで読める。
#: これを下回る `hold` が書かれていても、この時間までは伸ばす。
#: ナレーションが無い動画では、字幕を読み終える前に画面が変わるのが
#: いちばん起きやすい失敗である。
SUB_READ_CPS = 6.0
SUB_MIN_HOLD = 1.8

#: フォント。macOS に最初から入っているものだけを使う。
MONO_CANDIDATES = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
]
JP_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
UI_CANDIDATES = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"


def pick_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """候補の中から実在するフォントを開く。

    Args:
        candidates: 絶対パスの候補。上から順に試す。
        size: 文字サイズ。

    Returns:
        開けたフォント。

    Raises:
        SystemExit: どれも開けなかったとき。
    """
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    raise SystemExit(f"フォントが見つかりません: {candidates}")


MONO = pick_font(MONO_CANDIDATES, MONO_SIZE)
JP_MONO = pick_font(JP_CANDIDATES, MONO_SIZE)
JP_SUB = pick_font(JP_CANDIDATES, SUB_SIZE)
UI = pick_font(UI_CANDIDATES, 22)

#: 等幅 1 文字ぶんの幅。全角はこの二倍の桝目に入れる。
CELL_W = MONO.getlength("0")

#: カーソルの大きさ。実際のターミナルは桝目いっぱいの縦長の四角で、
#: 幅は半角一文字ぶん、高さは行の高さとほぼ同じである。
CURSOR_W = CELL_W
CURSOR_H = LINE_H - 4

#: 日本語フォントを等幅の字とそろえるための縦のずれ。二つの
#: フォントは ascent が違うので、その差だけ下げて描く。
JP_BASELINE_OFFSET = MONO.getmetrics()[0] - JP_MONO.getmetrics()[0]

#: 窓に実際に入る桁数と行数。タイトルに出す。
WIN_COLS = int((WIN_W - PAD_X * 2) // CELL_W)
WIN_ROWS = int((WIN_H - TITLEBAR_H - PAD_Y * 2) // LINE_H)


def load_emoji(ch: str, size: int) -> Image.Image | None:
    """カラー絵文字を画像として作る。

    Apple Color Emoji はビットマップ形式で、決まった大きさでしか
    読み込めない。文字として描くと失敗するので、規定の大きさで別に
    描いてから縮小する。

    Args:
        ch: 絵文字 1 文字。
        size: 仕上がりの高さ（ピクセル）。

    Returns:
        RGBA の画像。作れなければ None。
    """
    if not Path(EMOJI_FONT).exists():
        return None
    try:
        font = ImageFont.truetype(EMOJI_FONT, 160)
        base = Image.new("RGBA", (176, 176), (0, 0, 0, 0))
        ImageDraw.Draw(base).text((8, 8), ch, font=font, embedded_color=True)
        box = base.getbbox()
        if box is None:
            return None
        return base.crop(box).resize((size, size), Image.LANCZOS)
    except Exception:
        return None


EMOJI_IMG = load_emoji(PROMPT_EMOJI, MONO_SIZE)


def is_wide(ch: str) -> bool:
    """全角として扱う文字か判定する。

    Args:
        ch: 1 文字。

    Returns:
        全角なら True。
    """
    return unicodedata.east_asian_width(ch) in ("W", "F", "A")


def has_glyph(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    """フォントがその文字の字形を持っているか調べる。

    Args:
        font: 調べるフォント。
        ch: 1 文字。

    Returns:
        持っていれば True。
    """
    try:
        return font.getmask(ch).getbbox() is not None or ch.isspace()
    except Exception:
        return False


def color_of(name: str) -> tuple[int, int, int]:
    """色の名前を RGB に直す。

    Args:
        name: `COLORS` のキー。

    Returns:
        RGB のタプル。知らない名前なら既定の文字色。
    """
    return COLORS.get(name, FG)
