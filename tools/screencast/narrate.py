"""場面データの字幕から、場面ごとの音声を作る。

amapick の Kokoro 環境をそのまま呼ぶ。同じものを二重に入れると
PyTorch が数 GB 増えるため、環境は共有する。

**文ごとに分けて合成し、間に無音を挟む。** Kokoro に長い文字列を
一度に渡すと、句点があっても切らずに続けて読んでしまう (実測
2026-08-07)。amapick 側も同じ理由で文単位に分けて合成し、間に
0.6 秒の無音を入れている (`tts_generator.SEGMENT_GAP_SEC`)。

出来上がった音声の長さを `.timing.json` に書き出す。**画面の尺は
この実測値に合わせる。** 逆に画面へ音声を合わせようとすると、場面
ごとに読み上げ速度が変わって不自然になる。

使い方
    /Users/jacepark/ShortForm/amapick/.venv/bin/python narrate.py <場面データ.json>
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

# amapick のモジュールを読むためにパスを通す。
AMAPICK = Path("/Users/jacepark/ShortForm/amapick")
sys.path.insert(0, str(AMAPICK))

import soundfile as sf  # noqa: E402

from make.tts.tts_engine import synthesize_wav  # noqa: E402

#: 出力の sample rate。tts_engine の既定と合わせる。
SAMPLE_RATE = 24000

#: ボイスと速度。日本語 native のものを使う。af_* は英語モデルで
#: 日本語を読ませているため発音が崩れる (実測 2026-08-07)。
#:
#: 声は一人にそろえる。進行と結果で分けると掛け合いのように
#: 聞こえて、一人で解説している動画に合わない。
#:
#: native ボイスは読みが遅いので 1.3 倍で補正する
#: (amapick `common/tts_policy.py` の実測に合わせた)。
VOICE = "jf_nezumi"
SPEED = 1.3

#: 文と文の間に入れる無音の長さ (秒)。
GAP = 0.6

#: 字幕を文に切る位置。句点で切り、区切り文字は前の文に残す。
SENTENCE_END = re.compile(r"(?<=[。！？])")


def split_sentences(text: str) -> list[str]:
    """字幕を文に切る。

    Args:
        text: 字幕の全文。

    Returns:
        文の並び。空の要素は含まない。
    """
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def synth(text: str, voice: str) -> np.ndarray:
    """一文を合成して、波形の配列で返す。

    Args:
        text: 合成する文。
        voice: Kokoro のボイス名。

    Returns:
        float32 の 1 次元配列。
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = Path(tmp.name)

    try:
        synthesize_wav(
            output_path=str(path),
            text=text,
            lang="jp",
            voice=voice,
            sample_rate=SAMPLE_RATE,
            speed=SPEED,
        )
        audio, _ = sf.read(str(path))
    finally:
        path.unlink(missing_ok=True)

    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio, dtype=np.float32)


def silence(seconds: float) -> np.ndarray:
    """指定した長さの無音を作る。

    Args:
        seconds: 秒数。

    Returns:
        float32 の 1 次元配列。
    """
    return np.zeros(max(1, int(seconds * SAMPLE_RATE)), dtype=np.float32)


def build(text: str, voice: str) -> np.ndarray:
    """字幕ひとつぶんの音声を作る。

    Args:
        text: 字幕の全文。
        voice: Kokoro のボイス名。

    Returns:
        文と文の間に無音を挟んだ波形。
    """
    parts: list[np.ndarray] = []
    for i, sentence in enumerate(split_sentences(text)):
        if i:
            parts.append(silence(GAP))
        parts.append(synth(sentence, voice))
    return np.concatenate(parts) if parts else silence(0.1)


def main() -> None:
    """場面データを読み、字幕ごとに音声を作る。

    Raises:
        SystemExit: 引数が足りないとき。
    """
    if len(sys.argv) < 2:
        raise SystemExit("使い方: python3 narrate.py <場面データ.json>")

    src = Path(sys.argv[1]).resolve()
    data = json.loads(src.read_text(encoding="utf-8"))

    audio_dir = src.parent / "audio_gen"
    audio_dir.mkdir(exist_ok=True)

    timing: list[dict[str, object]] = []
    total = 0.0

    for i, scene in enumerate(data.get("scenes", [])):
        subtitle = scene.get("subtitle", "")
        typing = scene.get("typing_subtitle", "")

        entry: dict[str, object] = {"index": i}

        for key, text in (("subtitle", subtitle), ("typing_subtitle", typing)):
            if not text:
                continue

            name = f"{i:02d}_{key}.wav"
            wav = build(text, VOICE)
            sf.write(str(audio_dir / name), wav, SAMPLE_RATE)

            seconds = len(wav) / SAMPLE_RATE
            total += seconds
            entry[key] = {"audio": f"audio_gen/{name}", "seconds": round(seconds, 3)}
            print(f"{name:<28} {seconds:6.2f} 秒  {text[:24]}")

        if len(entry) > 1:
            timing.append(entry)

    out = src.with_suffix(".timing.json")
    out.write_text(
        json.dumps(
            {"voice": VOICE, "speed": SPEED, "gap": GAP,
             "total": round(total, 3), "scenes": timing},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"合計 {total:.2f} 秒 ({total / 60:.1f} 分)")
    print(f"書き出し: {out}")


if __name__ == "__main__":
    main()
