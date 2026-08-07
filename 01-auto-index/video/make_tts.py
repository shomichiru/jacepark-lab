"""ナレーション原稿から、カットごとの音声ファイルを作る。

amapick の Kokoro 環境をそのまま呼ぶ。同じものを二重に入れると
PyTorch が数 GB 増えるため、環境は共有する。

生成後、実測した長さを `timing.json` に書き出す。字幕のタイミングと
映像の尺合わせは、この実測値だけを見て決まる。

使い方
    /Users/jacepark/ShortForm/amapick/.venv/bin/python make_tts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# amapick のモジュールを読むためにパスを通す。
AMAPICK = Path("/Users/jacepark/ShortForm/amapick")
sys.path.insert(0, str(AMAPICK))

import soundfile as sf  # noqa: E402

from make.tts.tts_engine import synthesize_wav  # noqa: E402

HERE = Path(__file__).resolve().parent
NARRATION = HERE / "narration.json"
AUDIO_DIR = HERE / "audio"
TIMING = HERE / "timing.json"


def main() -> None:
    """カットごとに wav を作り、実測の長さを記録する。"""
    data = json.loads(NARRATION.read_text(encoding="utf-8"))
    voice = data["voice"]
    speed = data["speed"]

    AUDIO_DIR.mkdir(exist_ok=True)
    timing: list[dict[str, object]] = []
    total = 0.0

    for cut in data["cuts"]:
        cut_id = cut["id"]
        out = AUDIO_DIR / f"{cut_id}.wav"

        synthesize_wav(
            output_path=str(out),
            text=cut["text"],
            lang="jp",
            voice=voice,
            speed=speed,
        )

        info = sf.info(str(out))
        seconds = info.frames / info.samplerate
        total += seconds

        timing.append(
            {
                "id": cut_id,
                "audio": f"audio/{cut_id}.wav",
                "seconds": round(seconds, 3),
                "text": cut["text"],
            }
        )
        print(f"{cut_id:<14} {seconds:6.2f} 秒")

    TIMING.write_text(
        json.dumps(
            {"voice": voice, "speed": speed, "total": round(total, 3), "cuts": timing},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"合計 {total:.2f} 秒 ({total / 60:.1f} 分)")
    print(f"書き出し: {TIMING}")


if __name__ == "__main__":
    main()
