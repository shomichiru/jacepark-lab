"""場面データからスクリーンキャスト動画を作る。

画面を録画するのではなく、ターミナルの見た目そのものを描く。人が
操作する様子を真似るのではなく、コマンドと出力だけを見せる。狙いは
「そのスクリプトで問題を解いた」ことを伝えることであって、操作の
再現ではないためである。

字幕は画面の中に直接描く。ffmpeg の字幕焼き込みを使わないので
libass の有無に左右されない。位置が固定なので、後からフレーム単位で
テキストを取り出すのも容易になる。

前提
    Pillow が入っていること
    ffmpeg があること

`narrate.py` を先に実行して `.timing.json` があれば、その実測値に
画面の尺を合わせ、音声も一緒に入れる。無ければ字幕を読む時間から
尺を決め、音声なしで作る。**画面に音声を合わせない。** そちらへ倒すと
場面ごとに読み上げ速度が変わって不自然になる。

使い方
    python3 render.py <場面データ.json> [出力.mp4]

    出力を省くと、場面データと同じ場所に同じ名前の mp4 を作る。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import theme as T
from scenes import Row, Scene, load


def draw_mixed(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
) -> int:
    """等幅の桝目に文字を置いていく。

    SF Mono は日本語や全角記号の字形を持たないため、そのまま描くと
    その文字だけ消える (実測 2026-08-07: 「3 件」が「3」になった)。
    無い字は日本語フォントで補う。

    ただし日本語フォントはプロポーショナルなので、そのまま並べると
    桁がずれ、縦位置も等幅の字とそろわない。実際のターミナルと同じ
    ように、全角は半角二つ分の桝目に入れ、その中で中央に置く。縦は
    等幅フォントの ascent を基準にそろえる。

    Args:
        draw: 描画対象。
        x: 描き始めの x 座標。
        y: 桝目の上端の y 座標。
        text: 描く文字列。
        color: 文字色。

    Returns:
        描き終えた位置の x 座標。
    """
    cx = float(x)
    for ch in text:
        cell = T.CELL_W * (2 if T.is_wide(ch) else 1)

        if T.has_glyph(T.MONO, ch):
            draw.text((cx, y), ch, font=T.MONO, fill=color)
        else:
            w = draw.textlength(ch, font=T.JP_MONO)
            draw.text(
                (cx + (cell - w) / 2, y + T.JP_BASELINE_OFFSET),
                ch,
                font=T.JP_MONO,
                fill=color,
            )
        cx += cell
    return int(cx)


def draw_window(draw: ImageDraw.ImageDraw, title: str) -> tuple[int, int]:
    """ターミナルの窓枠を描く。

    Args:
        draw: 描画対象。
        title: タイトルバーに出す名前。

    Returns:
        本文の描き始め座標 (x, y)。
    """
    x0, y0 = T.WIN_MARGIN_X, T.WIN_TOP
    x1, y1 = x0 + T.WIN_W, y0 + T.WIN_H

    draw.rounded_rectangle([x0, y0, x1, y1], radius=T.WIN_RADIUS, fill=T.BG)
    draw.rounded_rectangle(
        [x0, y0, x1, y0 + T.TITLEBAR_H], radius=T.WIN_RADIUS, fill=T.TITLEBAR
    )
    draw.rectangle(
        [x0, y0 + T.TITLEBAR_H - T.WIN_RADIUS, x1, y0 + T.TITLEBAR_H], fill=T.TITLEBAR
    )
    draw.line(
        [x0, y0 + T.TITLEBAR_H, x1, y0 + T.TITLEBAR_H], fill=T.TITLEBAR_LINE, width=1
    )

    cy = y0 + T.TITLEBAR_H // 2
    for i, color in enumerate(T.LIGHTS):
        cx = x0 + T.LIGHT_X + i * T.LIGHT_GAP
        draw.ellipse(
            [cx - T.LIGHT_R, cy - T.LIGHT_R, cx + T.LIGHT_R, cy + T.LIGHT_R], fill=color
        )

    label = f"{title} — -zsh — {T.WIN_COLS}×{T.WIN_ROWS}"
    bbox = draw.textbbox((0, 0), label, font=T.UI)
    draw.text(
        (
            (x0 + x1) // 2 - (bbox[2] - bbox[0]) // 2,
            cy - (bbox[3] - bbox[1]) // 2 - bbox[1],
        ),
        label,
        font=T.UI,
        fill=T.TITLE_FG,
    )

    return x0 + T.PAD_X, y0 + T.TITLEBAR_H + T.PAD_Y


def draw_prompt(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int) -> int:
    """プロンプトを描き、続きを描く x 座標を返す。

    絵文字は文字として描けないので、画像として貼り込む。

    Args:
        img: 貼り込み先の画像。
        draw: 描画対象。
        x: 描き始めの x 座標。
        y: 描き始めの y 座標。

    Returns:
        コマンド本体を描き始める x 座標。
    """
    if T.EMOJI_IMG is None:
        x = draw_mixed(draw, x, y, T.PROMPT_FALLBACK, T.USER)
        return draw_mixed(draw, x, y, " gen$ ", T.FG)

    x = draw_mixed(draw, x, y, T.PROMPT_HEAD, T.USER)
    img.paste(T.EMOJI_IMG, (x, y + 3), T.EMOJI_IMG)
    x += T.EMOJI_IMG.width
    x = draw_mixed(draw, x, y, T.PROMPT_HEAD_TAIL, T.USER)
    return draw_mixed(draw, x, y, " gen$ ", T.FG)


def draw_subtitle(img: Image.Image, subtitle: str) -> None:
    """字幕を画面下部に描く。

    Args:
        img: 描画対象。
        subtitle: 表示する文字列。
    """
    if not subtitle:
        return

    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), subtitle, font=T.JP_SUB)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    box_w = tw + T.SUB_PAD * 2
    box_h = th + T.SUB_PAD * 2
    bx = (T.WIDTH - box_w) // 2
    by = T.HEIGHT - int(T.HEIGHT * T.SUB_BOTTOM_RATIO) - box_h

    layer = Image.new("RGBA", (T.WIDTH, T.HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [bx, by, bx + box_w, by + box_h],
        radius=T.SUB_RADIUS,
        fill=(*T.SUB_BG, T.SUB_ALPHA),
    )
    img.paste(
        Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0)
    )

    ImageDraw.Draw(img).text(
        (bx + T.SUB_PAD - bbox[0], by + T.SUB_PAD - bbox[1]),
        subtitle,
        font=T.JP_SUB,
        fill=T.FG,
    )


def draw_frame(
    title: str,
    rows: list[Row],
    subtitle: str,
    cursor: bool,
    note: str = "",
) -> Image.Image:
    """1 フレームを描く。

    Args:
        title: 窓のタイトルに出す名前。
        rows: 画面に出ている行。
        subtitle: 下部に出す文字列。
        cursor: 末尾にカーソルを出すか。
        note: 指定があればターミナルを出さず、この文言だけを見せる。

    Returns:
        描き終えた画像。
    """
    img = Image.new("RGB", (T.WIDTH, T.HEIGHT), T.DESKTOP)
    draw = ImageDraw.Draw(img)

    if note:
        bbox = draw.textbbox((0, 0), note, font=T.JP_SUB)
        draw.text(
            (
                (T.WIDTH - (bbox[2] - bbox[0])) // 2 - bbox[0],
                (T.HEIGHT - (bbox[3] - bbox[1])) // 2 - bbox[1],
            ),
            note,
            font=T.JP_SUB,
            fill=T.FG,
        )
        draw_subtitle(img, subtitle)
        return img

    x0, y = draw_window(draw, title)

    # 実際のターミナルは上から順に埋まっていき、窓を越えたところで
    # 初めて上へ流れていく。最初から下寄せにすると、開いた直後から
    # 画面の底にプロンプトがある不自然な絵になる (実測 2026-08-07)。
    shown = rows[-T.WIN_ROWS:] if len(rows) > T.WIN_ROWS else rows

    last_x = x0
    for row in shown:
        x = draw_prompt(img, draw, x0, y) if row.prompt else x0
        last_x = draw_mixed(draw, x, y, row.text, T.color_of(row.color))
        y += T.LINE_H

    if cursor and shown:
        top = y - T.LINE_H
        draw.rectangle(
            [
                last_x + 2,
                top,
                last_x + 2 + T.CURSOR_W,
                top + T.CURSOR_H,
            ],
            fill=T.FG,
        )

    draw_subtitle(img, subtitle)
    return img


def load_timing(src: Path) -> dict[int, dict]:
    """`narrate.py` が書いた音声の実測値を読む。

    Args:
        src: 場面データのパス。

    Returns:
        場面の番号をキーにした実測値。ファイルが無ければ空の辞書。
    """
    path = src.with_suffix(".timing.json")
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(item["index"]): item for item in data.get("scenes", [])}


def voice_len(timing: dict[int, dict], index: int, key: str) -> float:
    """その場面の音声の長さを返す。

    Args:
        timing: `load_timing` の結果。
        index: 場面の番号。
        key: "subtitle" か "typing_subtitle"。

    Returns:
        秒数。音声が無ければ 0。
    """
    entry = timing.get(index, {}).get(key)
    return float(entry["seconds"]) if entry else 0.0


def read_time(subtitle: str, hold: float) -> float:
    """字幕を読み終えるのに要る時間を返す。

    Args:
        subtitle: 表示する字幕。
        hold: 場面データに書かれた秒数。

    Returns:
        実際に使う秒数。書かれた値がこれより短ければ伸ばす。
    """
    if not subtitle:
        return hold
    need = max(T.SUB_MIN_HOLD, len(subtitle) / T.SUB_READ_CPS)
    return max(hold, need)


class Writer:
    """フレームを連番の画像として書き出す。

    Attributes:
        dst: 書き出し先のディレクトリ。
        count: これまでに書いた枚数。
    """

    def __init__(self, dst: Path) -> None:
        """書き出し先を用意する。

        Args:
            dst: 書き出し先のディレクトリ。中身は消される。
        """
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        self.dst = dst
        self.count = 0

    def hold(self, img: Image.Image, seconds: float) -> None:
        """同じ絵を指定した秒数ぶん書く。

        Args:
            img: 書き出す画像。
            seconds: 秒数。
        """
        for _ in range(max(1, round(seconds * T.FPS))):
            img.save(self.dst / f"{self.count:06d}.png")
            self.count += 1


def render(
    title: str,
    scenes: list[Scene],
    work: Path,
    timing: dict[int, dict],
    plan: list[tuple[float, str | None]],
) -> int:
    """場面の並びをフレーム画像として書き出す。

    Args:
        title: 窓のタイトルに出す名前。
        scenes: 描く場面。
        work: フレームを置くディレクトリ。
        timing: 音声の実測値。空なら字幕を読む時間で尺を決める。
        plan: 音声をつなぐ順序を書き足していく先。
            (秒数, 音声ファイル名または None) の並びになる。

    Returns:
        書き出したフレーム数。
    """
    writer = Writer(work)
    rows: list[Row] = []
    spoken: set[str] = set()

    def slot(index: int, key: str, text: str, fallback: float) -> tuple[float, str | None]:
        """その場面で使う秒数と音声を決める。

        同じ字幕が続けて出ることがある (打っている間と結果を見せる間で
        同じ文を使う場合など)。同じ文を二度読ませると不自然なので、
        二度目は無音にして尺だけ取る。

        Args:
            index: 場面の番号。
            key: "subtitle" か "typing_subtitle"。
            text: 字幕の文字列。
            fallback: 音声が無いときに使う秒数。

        Returns:
            (秒数, 音声ファイル名または None)。
        """
        entry = timing.get(index, {}).get(key)
        if not entry:
            return fallback, None

        if text in spoken:
            return float(entry["seconds"]), None

        spoken.add(text)
        return float(entry["seconds"]), str(entry["audio"])

    for index, scene in enumerate(scenes):
        if scene.kind == "clear":
            rows = []
            continue

        if scene.kind == "note":
            seconds, audio = slot(
                index, "subtitle", scene.subtitle,
                read_time(scene.subtitle, scene.hold),
            )
            img = draw_frame(title, [], scene.subtitle, False, note=scene.note)
            writer.hold(img, seconds)
            plan.append((seconds, audio))
            continue

        if scene.kind == "command":
            sub = scene.typing_subtitle or scene.subtitle

            # 字幕を先に出し、プロンプトだけ置いた状態で待つ。実際の
            # ターミナルはプロンプトが先に出ていて、その後ろでカーソルが
            # 点滅している。入力の一文字目と同時に現れることはない。
            #
            # 字幕はこのあと打ち終わるまで出したままにする。打ち終えて
            # から字幕を変え、また止まって次を打つ、という進み方をすると
            # 段取りが一つずつ切れて機械的に見える (実測 2026-08-07)。
            key = "typing_subtitle" if scene.typing_subtitle else "subtitle"
            typing_sec = len(scene.text) / T.TYPE_CPS
            voice, audio = slot(
                index, key, sub, T.SUB_LEAD + typing_sec + scene.hold,
            )

            # 音声が打ち終わりより長ければ、その分だけ後ろで待つ。
            # 音声を途中で切らないためである。
            tail = max(scene.hold + T.RUN_DELAY, voice - T.SUB_LEAD - typing_sec)
            total = T.SUB_LEAD + typing_sec + tail

            waiting = rows + [Row("", "fg", True)]
            writer.hold(draw_frame(title, waiting, sub, True), T.SUB_LEAD)

            for i in range(1, len(scene.text) + 1):
                shown = rows + [Row(scene.text[:i], "fg", True)]
                writer.hold(draw_frame(title, shown, sub, True), 1 / T.TYPE_CPS)

            rows = rows + [Row(scene.text, "fg", True)]

            # 打ち終わったら、字幕はそのままで実行に移る。
            writer.hold(draw_frame(title, rows, sub, True), tail)
            plan.append((total, audio))
            continue

        # output — 実行は一瞬なので待たせず、すぐ結果を出す。字幕は
        # 結果と同時に切り替える。ここで待つと、出力を見る前に説明を
        # 読まされる形になり、順序が逆になる。
        rows = rows + scene.rows
        idle = rows + [Row("", "fg", True)]

        seconds, audio = slot(
            index, "subtitle", scene.subtitle,
            read_time(scene.subtitle, scene.hold),
        )
        writer.hold(draw_frame(title, idle, scene.subtitle, True), seconds)
        plan.append((seconds, audio))
        rows = idle[:-1]

    # 最後に余韻を置く。喋り終わってすぐ切れると、まだ続きがあるのに
    # 打ち切られたように見える。
    last = scenes[-1]
    if last.kind == "note":
        tail = draw_frame(title, [], last.subtitle, False, note=last.note)
    else:
        tail = draw_frame(title, rows + [Row("", "fg", True)], last.subtitle, True)

    writer.hold(tail, T.OUTRO)
    plan.append((T.OUTRO, None))

    return writer.count


def run_ffmpeg(args: list[str]) -> None:
    """ffmpeg を実行する。

    Args:
        args: ffmpeg に渡す引数。

    Raises:
        SystemExit: 実行に失敗したとき。
    """
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"ffmpeg に失敗しました: {' '.join(args[:6])} ...")


def build_audio(plan: list[tuple[float, str | None]], base: Path, out: Path) -> None:
    """場面の順に音声をつなぎ、1 本の wav にする。

    音声が無い場面は、その秒数ぶんの無音で埋める。音声が場面より
    短い場合も、残りを無音で埋めて頭の位置をそろえる。

    Args:
        plan: (秒数, 音声ファイル名または None) の並び。
        base: 音声ファイルの基準となるディレクトリ。
        out: 出力する wav のパス。
    """
    import numpy as np
    import soundfile as sf

    rate = 24000
    parts: list[np.ndarray] = []

    for seconds, audio in plan:
        frames = max(1, int(seconds * rate))

        if audio is None:
            parts.append(np.zeros(frames, dtype=np.float32))
            continue

        wav, sr = sf.read(str(base / audio))
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        wav = np.asarray(wav, dtype=np.float32)

        if len(wav) < frames:
            wav = np.concatenate([wav, np.zeros(frames - len(wav), dtype=np.float32)])
        parts.append(wav[:frames])

    sf.write(str(out), np.concatenate(parts), rate)


def encode(work: Path, out: Path, audio: Path | None) -> None:
    """フレーム画像を mp4 にまとめる。

    Args:
        work: フレームが入っているディレクトリ。
        out: 出力先。
        audio: 入れる音声。無ければ None。

    Raises:
        SystemExit: ffmpeg に失敗したとき。
    """
    args = [
        "-framerate", str(T.FPS),
        "-i", str(work / "%06d.png"),
    ]
    if audio is not None:
        args += ["-i", str(audio)]

    args += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
    ]
    if audio is not None:
        args += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

    run_ffmpeg(args + [str(out)])


def main() -> None:
    """場面データを読み、動画を作る。

    Raises:
        SystemExit: 引数が足りないとき。
    """
    if len(sys.argv) < 2:
        raise SystemExit("使い方: python3 render.py <場面データ.json> [出力.mp4]")

    src = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.with_suffix(".mp4")

    title, scenes = load(src)
    timing = load_timing(src)
    print(f"場面 {len(scenes)} 件 / 窓 {T.WIN_COLS}×{T.WIN_ROWS}")
    print("音声: " + ("実測値に合わせます" if timing else "ありません"))

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "frames"
        plan: list[tuple[float, str | None]] = []
        count = render(title, scenes, work, timing, plan)
        print(f"フレーム {count} 枚 ({count / T.FPS:.1f} 秒)")

        wav: Path | None = None
        if timing:
            wav = Path(tmp) / "voice.wav"
            build_audio(plan, src.parent, wav)

        encode(work, out, wav)

    print(f"完成: {out}")


if __name__ == "__main__":
    main()
