# -*- coding: utf-8 -*-
# ============================================================
# 官方 GPT-SoVITS 原生直测（绕过本服务 tts_api，直接调引擎 api.py）
# 目的：区分"漏字/合成异常"是音色模型本身的问题，还是 tts_service 处理环节的问题
#
# 依赖本机已就位（与 DEPLOY.md 约定一致）：
#   <仓库根>\gptsovits\GPT-SoVITS\           官方引擎（含 pretrained_models 基座）
#   <仓库根>\tts_service\models\<角色名>\     音色模型 4 件套
# 也可用环境变量覆盖：GSV_ROOT / GSV_MODELS_DIR
#
# 用法：python 官方直测.py
# ============================================================
import os
import sys
import io

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # tests\ 的上一级 = 仓库根

GSV_ROOT = os.environ.get("GSV_ROOT") or os.path.join(PROJECT_ROOT, "gptsovits", "GPT-SoVITS")
MODELS_DIR = os.environ.get("GSV_MODELS_DIR") or os.path.join(PROJECT_ROOT, "tts_service", "models")
# 要直测的角色（= models 目录下的角色文件夹名，改成你实际有的角色）
ROLE = os.environ.get("ROLE", "fengyanlin")
MODEL_DIR = os.path.join(MODELS_DIR, ROLE)
OUT_DIR = os.path.join(SCRIPT_DIR, "官方直测")

os.chdir(GSV_ROOT)
if GSV_ROOT not in sys.path:
    sys.path.insert(0, GSV_ROOT)

gpt_path = os.path.join(MODEL_DIR, ROLE + ".ckpt")
sovits_path = os.path.join(MODEL_DIR, ROLE + ".pth")
ref = os.path.join(MODEL_DIR, "ref.wav")
with open(os.path.join(MODEL_DIR, "ref_text.txt"), encoding="utf-8") as f:
    ref_text = f.read().strip()

# 模拟 tts_api 启动时的 argv（hubert/roberta 预训练模型路径）
sys.argv = [
    "api.py",
    "-s", sovits_path,
    "-g", gpt_path,
    "-dr", ref,
    "-dt", ref_text,
    "-dl", "zh",
    "-hb", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-hubert-base"),
    "-b", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-roberta-wwm-ext-large"),
    "-p", "9999",
]
import api as gpt_api  # noqa: E402

import numpy as np
import soundfile as sf

gpt = gpt_api.get_gpt_weights(gpt_path)
sovits_w = gpt_api.get_sovits_weights(sovits_path)
speaker = gpt_api.Speaker(name=ROLE, gpt=gpt, sovits=sovits_w)
gpt_api.speaker_list["default"] = speaker
print("模型加载完成: %s" % MODEL_DIR, flush=True)

CASES = [
    ("sentence17", "路边的花开得正艳，小鸟在枝头歌唱。"),
    ("sentence30", "今天天气真不错，阳光洒满大地，我决定出门走走，感受春天的气息。"),
    ("full48", "今天天气真不错，阳光洒满大地，我决定出门走走，感受春天的气息。路边的花开得正艳，小鸟在枝头歌唱。"),
]
os.makedirs(OUT_DIR, exist_ok=True)

for name, text in CASES:
    gen = gpt_api.get_tts_wav(
        ref_wav_path=ref,
        prompt_text=ref_text,
        prompt_language="zh",
        text=text,
        text_language="zh",
        top_k=12, top_p=0.9, temperature=0.7, speed=1.0,
        inp_refs=[], sample_steps=32, if_sr=False,
    )
    chunks = []
    sr = 32000
    for item in gen:
        data = item[0] if isinstance(item, tuple) else item
        if isinstance(data, bytes):
            a, s = sf.read(io.BytesIO(data), dtype="float32")
            sr = s
            chunks.append(a)
        elif hasattr(data, "cpu"):
            chunks.append(data.cpu().numpy())
        else:
            chunks.append(np.asarray(data))
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    out = os.path.join(OUT_DIR, name + ".wav")
    sf.write(out, audio, sr)
    print("%s: %d 样本, %.2f 秒 -> %s" % (name, len(audio), len(audio) / sr, out), flush=True)
print("DONE", flush=True)
