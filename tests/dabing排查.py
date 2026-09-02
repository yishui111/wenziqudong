# -*- coding: utf-8 -*-
# ============================================================
# 角色合成异常排查：模型训练问题 vs 参考音频(ref.wav/ref_text.txt)配置问题
# case A: 角色A 自己的 ref -> 复现
# case B: 角色B 合格 ref（3~10 秒）-> 测试模型本身能力
# 同一文本、同一参数，对比合成时长与内容。
#
# 依赖本机已就位（与 DEPLOY.md 约定一致）：
#   <仓库根>\gptsovits\GPT-SoVITS\           官方引擎（含 pretrained_models 基座）
#   <仓库根>\tts_service\models\<角色名>\     音色模型 4 件套
# 可用环境变量覆盖：GSV_ROOT / GSV_MODELS_DIR / ROLE_A / ROLE_B
#
# 用法：python dabing排查.py   （角色名建议改成你 models 里实际存在的角色）
# ============================================================
import os
import sys
import io

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # tests\ 的上一级 = 仓库根

GSV_ROOT = os.environ.get("GSV_ROOT") or os.path.join(PROJECT_ROOT, "gptsovits", "GPT-SoVITS")
MODELS_DIR = os.environ.get("GSV_MODELS_DIR") or os.path.join(PROJECT_ROOT, "tts_service", "models")
ROLE_A = os.environ.get("ROLE_A", "dabing")   # 被排查角色（怀疑 ref 配置有问题）
ROLE_B = os.environ.get("ROLE_B", "azhong")   # 对照角色（ref 已知合格）
A_DIR = os.path.join(MODELS_DIR, ROLE_A)
B_DIR = os.path.join(MODELS_DIR, ROLE_B)
OUT = os.path.join(SCRIPT_DIR, "ref排查输出")

os.chdir(GSV_ROOT)
sys.path.insert(0, GSV_ROOT)


def read_ref(role_dir):
    ref = os.path.join(role_dir, "ref.wav")
    ref_text = open(os.path.join(role_dir, "ref_text.txt"), encoding="utf-8").read().strip()
    return ref, ref_text


a_gpt = os.path.join(A_DIR, ROLE_A + ".ckpt")
a_sovits = os.path.join(A_DIR, ROLE_A + ".pth")
a_ref, a_ref_text = read_ref(A_DIR)
b_ref, b_ref_text = read_ref(B_DIR)

sys.argv = ["api.py", "-s", a_sovits, "-g", a_gpt, "-dr", a_ref, "-dt", a_ref_text, "-dl", "zh",
            "-hb", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-hubert-base"),
            "-b", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-roberta-wwm-ext-large"),
            "-p", "9999"]
import api as gpt_api  # noqa: E402

import numpy as np
import soundfile as sf

gpt = gpt_api.get_gpt_weights(a_gpt)
sovits_w = gpt_api.get_sovits_weights(a_sovits)
gpt_api.speaker_list["default"] = gpt_api.Speaker(name=ROLE_A, gpt=gpt, sovits=sovits_w)
print("MODEL_LOADED: %s (对照 ref 来自 %s)" % (A_DIR, B_DIR), flush=True)

os.makedirs(OUT, exist_ok=True)
CASES = [
    ("A_own_ref", "大家好，我是" + ROLE_A + "，很高兴见到你们。", a_ref, a_ref_text),
    ("B_other_ref", "大家好，我是" + ROLE_A + "，很高兴见到你们。", b_ref, b_ref_text),
    ("B2_other_ref_long", "今天天气真不错，阳光洒满大地，我决定出门走走，感受春天的气息。", b_ref, b_ref_text),
]


def synth(name, text, ref, ref_text):
    gen = gpt_api.get_tts_wav(
        ref_wav_path=ref, prompt_text=ref_text, prompt_language="zh",
        text=text, text_language="zh",
        top_k=12, top_p=0.9, temperature=0.7, speed=1.0,
        inp_refs=[], sample_steps=32, if_sr=False,
    )
    chunks, sr = [], 32000
    for item in gen:
        data = item[0] if isinstance(item, tuple) else item
        if isinstance(data, bytes):
            a, s = sf.read(io.BytesIO(data), dtype="float32"); sr = s; chunks.append(a)
        elif hasattr(data, "cpu"):
            chunks.append(data.cpu().numpy())
        else:
            chunks.append(np.asarray(data))
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    sf.write(os.path.join(OUT, name + ".wav"), audio, sr)
    print("%s: %.2f 秒 -> %s" % (name, len(audio) / sr, os.path.join(OUT, name + ".wav")), flush=True)


for name, text, ref, ref_text in CASES:
    try:
        synth(name, text, ref, ref_text)
    except Exception as e:  # noqa: BLE001
        print("%s: ERROR %s" % (name, e), flush=True)
print("DONE", flush=True)
