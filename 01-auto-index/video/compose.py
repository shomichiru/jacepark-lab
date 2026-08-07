"""カットごとの録画と音声を合成して、1 本の動画にする。

録画の長さは気にしなくてよい。ナレーションの長さに合わせて
こちらで調整する。

- 録画がナレーションより長い → 等倍速を保ったまま前から切る
- 録画がナレーションより短い → 最後のフレームを静止で伸ばす

倍速にしない理由: 画面のタイピングが不自然に速くなり、
何をしているか読めなくなるため。切る方が見やすい。

前提
    ffmpeg がインストールされていること
    recordings/ にカットごとの録画があること
    make_tts.py を実行済みで audio/ と timing.json があること

使い方
    python3 compose.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMING = HERE / "timing.json"
RECORDINGS = HERE / "recordings"
WORK = HERE / "work"
OUT = HERE / "output.mp4"

#: 出力の解像度。録画がこれと違ってもここに合わせる。
WIDTH, HEIGHT = 1920, 1080


def run(args: list[str]) -> None:
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
        raise SystemExit(f"ffmpeg 失敗: {' '.join(args[:6])} ...")


def probe_duration(path: Path) -> float:
    """動画の長さを秒で返す。

    Args:
        path: 対象ファイル。

    Returns:
        秒数。
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def build_cut(cut_id: str, seconds: float) -> Path:
    """1 カットを、ナレーションの長さに合わせた mp4 にする。

    Args:
        cut_id: カット識別子。
        seconds: 合わせる長さ（秒）。

    Returns:
        生成した中間ファイルのパス。

    Raises:
        SystemExit: 録画ファイルが無いとき。
    """
    source = next(RECORDINGS.glob(f"{cut_id}.*"), None)
    if source is None:
        raise SystemExit(f"録画がありません: {RECORDINGS}/{cut_id}.*")

    out = WORK / f"{cut_id}.mp4"
    length = probe_duration(source)
    scale = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )

    if length >= seconds:
        # 長い場合は前から必要な分だけ使う。
        run(
            [
                "-i", str(source),
                "-t", f"{seconds:.3f}",
                "-vf", scale,
                "-r", "30",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-an",
                str(out),
            ]
        )
        note = f"{length:.1f}s → 前から {seconds:.1f}s"
    else:
        # 短い場合は最後のフレームで埋める。
        run(
            [
                "-i", str(source),
                "-vf", f"{scale},tpad=stop_mode=clone:stop_duration={seconds - length:.3f}",
                "-t", f"{seconds:.3f}",
                "-r", "30",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-an",
                str(out),
            ]
        )
        note = f"{length:.1f}s → 静止で {seconds:.1f}s まで延長"

    print(f"  {cut_id:<14} {note}")
    return out


def main() -> None:
    """全カットを合成して 1 本にする。"""
    if not TIMING.exists():
        raise SystemExit("timing.json がありません。先に make_tts.py を実行してください。")
    if not RECORDINGS.is_dir():
        raise SystemExit(f"録画フォルダがありません: {RECORDINGS}")

    data = json.loads(TIMING.read_text(encoding="utf-8"))
    WORK.mkdir(exist_ok=True)

    print("カットを整えています")
    video_parts: list[Path] = []
    audio_parts: list[Path] = []

    for cut in data["cuts"]:
        video_parts.append(build_cut(cut["id"], float(cut["seconds"])))
        audio_parts.append(HERE / cut["audio"])

    # 連結リスト。
    v_list = WORK / "video.txt"
    a_list = WORK / "audio.txt"
    v_list.write_text(
        "\n".join(f"file '{p}'" for p in video_parts) + "\n", encoding="utf-8"
    )
    a_list.write_text(
        "\n".join(f"file '{p}'" for p in audio_parts) + "\n", encoding="utf-8"
    )

    print("結合しています")
    merged_v = WORK / "merged_video.mp4"
    merged_a = WORK / "merged_audio.wav"
    run(["-f", "concat", "-safe", "0", "-i", str(v_list), "-c", "copy", str(merged_v)])
    run(["-f", "concat", "-safe", "0", "-i", str(a_list), "-c", "copy", str(merged_a)])

    print("字幕を焼き込んでいます")
    run(
        [
            "-i", str(merged_v),
            "-i", str(merged_a),
            "-vf",
            "subtitles=subtitle.srt:force_style="
            "'FontName=Hiragino Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
            "Alignment=2,MarginV=48'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(OUT),
        ]
    )

    print()
    print(f"完成: {OUT}  ({probe_duration(OUT):.1f} 秒)")


if __name__ == "__main__":
    main()
