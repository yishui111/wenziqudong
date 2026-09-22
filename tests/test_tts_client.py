# -*- coding: utf-8 -*-
r"""文字变声音服务测试客户端：POST /tts 合成文字为 wav，结果存 tests\ 下。

用法：
    python tests\test_tts_client.py --character liejun --text "大家好，我是雷军。"
    python tests\test_tts_client.py                          # 角色留空则自动取 /models 第一个可用角色

前置：服务已启动（双击 一键启动文字变声音.bat，端口固定 18062）。
"""
import argparse
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18062")
    ap.add_argument("--text", default="大家好，我是文字变声音，现在测试合成效果。")
    ap.add_argument("--character", default="", help="角色名（= tts_service\\models 下的目录名）；留空自动选第一个可用角色")
    ap.add_argument("--speed", default="1.0")
    ap.add_argument("--out", default=os.path.join(HERE, "tts_test_out.wav"))
    args = ap.parse_args()

    r = requests.get(args.base + "/health", timeout=10)
    print("health:", r.status_code, r.json())

    r = requests.get(args.base + "/models", timeout=10)
    print("models:", r.json())

    character = args.character
    if not character:
        ready = [m["name"] for m in r.json().get("models", []) if m.get("ready")]
        if not ready:
            print("error: 没有任何可用角色，请先把音色模型（4件套）放入 tts_service\\models\\<角色名>\\")
            sys.exit(1)
        character = ready[0]
        print("auto pick character:", character)

    t0 = time.time()
    r = requests.post(args.base + "/tts", data={
        "text": args.text,
        "character": character,
        "speed": args.speed,
    }, timeout=600)
    print("tts status:", r.status_code, "elapsed: %.1fs" % (time.time() - t0))
    if r.status_code == 200:
        with open(args.out, "wb") as f:
            f.write(r.content)
        print("saved:", args.out, "size:", len(r.content))
        import soundfile as sf
        y, sr = sf.read(args.out)
        print("audio seconds: %.2f, sr: %d" % (len(y) / sr, sr))
    else:
        print("error:", r.text[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
