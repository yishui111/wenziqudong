# -*- coding: utf-8 -*-
"""
文字驱动语音服务（独立项目，完全自包含）
=============================================================
输入文字 -> 用训练好的 GPT-SoVITS 音色模型合成语音（TTS），快且自然。

自动读取本项目的模型目录（目录扫描，放进去即识别）：
    tts_service\\models\\<角色名>\\
        <角色名>.ckpt     GPT 权重（文本->语义）
        <角色名>.pth      SoVITS 权重（语义->语音）
        ref.wav           参考音频（该角色一段干净人声，3~10 秒）
        ref_text.txt      参考音频对应的文字（UTF-8）

模型来源：训练中心（xunlianzhongxin）训练完成后生成"交付模型\\<角色名>\\"
文件夹，把整个文件夹复制到 tts_service\\models\\ 即可，本服务立刻自动识别。

本项目完全自包含：运行时（runtime\\py312）、GPT-SoVITS 引擎（gptsovits\\GPT-SoVITS）
全部内置，复制整个项目文件夹到任意电脑双击启动即可，不依赖任何外部项目。
"""

import io
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import uuid

import numpy as np
import soundfile as sf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# GPT-SoVITS 推理引擎：项目内置（gptsovits\GPT-SoVITS，随项目一起复制，完全自包含），可用 GSV_ROOT 覆盖
GSV_ROOT = os.environ.get("GSV_ROOT") or os.path.join(PROJECT_ROOT, "gptsovits", "GPT-SoVITS")
# 解耦：模型直接发布到本项目的模型目录（训练中心-文字驱动模式发布到这里），本服务自己读自己的模型
GSV_MODELS_DIR = os.environ.get("GSV_MODELS_DIR", os.path.join(SCRIPT_DIR, "models"))
API_PORT = int(os.environ.get("TTS_API_PORT", "8060"))
# 推理设备：cuda（默认，需显卡）或 cpu（不吃显存，适合 8G 显卡与 LLM 同机跑）
TTS_DEVICE = (os.environ.get("TTS_DEVICE", "cuda") or "cuda").strip().lower()
if TTS_DEVICE not in ("cuda", "cpu"):
    TTS_DEVICE = "cuda"
# 启动预热的默认音色：与 Open WebUI 默认音色保持一致（默认 azhong），
# 保证不改音色时首次朗读不用等模型加载。可被 TTS_DEFAULT_VOICE 覆盖。
TTS_DEFAULT_VOICE = (os.environ.get("TTS_DEFAULT_VOICE", "azhong") or "azhong").strip()
# GPT 采样步数：64（默认，更稳、减少跳读漏字；速度稍慢）/ 32（快，偶发跳读）。
# 想更快可设 TTS_SAMPLE_STEPS=32。
TTS_SAMPLE_STEPS = int(os.environ.get("TTS_SAMPLE_STEPS", "64") or "64")
CHARACTER_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]+$")

TMP_ROOT = os.environ.get("TTS_TMP_ROOT", os.path.join(SCRIPT_DIR, "tmp"))
os.makedirs(TMP_ROOT, exist_ok=True)
os.makedirs(os.path.join(TMP_ROOT, "matplotlib"), exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(TMP_ROOT, "matplotlib"))
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(TMP_ROOT, "numba"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("wenziqudong_tts")


def list_role_dirs():
    if not os.path.isdir(GSV_MODELS_DIR):
        return []
    out = []
    for name in sorted(os.listdir(GSV_MODELS_DIR)):
        p = os.path.join(GSV_MODELS_DIR, name)
        if os.path.isdir(p) and CHARACTER_RE.match(name or ""):
            out.append((name, p))
    return out


def discover_roles():
    """扫描模型目录，返回每个角色的状态。ready=True 表示可直接合成。"""
    roles = {}
    for name, d in list_role_dirs():
        # 新约定：<角色名>.ckpt / <角色名>.pth；兼容旧模型：目录内任意 .ckpt / .pth
        gpt = os.path.join(d, name + ".ckpt")
        sovits = os.path.join(d, name + ".pth")
        if not os.path.isfile(gpt):
            ckpts = sorted(x for x in os.listdir(d) if x.lower().endswith(".ckpt"))
            gpt = os.path.join(d, ckpts[0]) if ckpts else gpt
        if not os.path.isfile(sovits):
            pths = sorted(x for x in os.listdir(d) if x.lower().endswith(".pth"))
            sovits = os.path.join(d, pths[0]) if pths else sovits
        ref = os.path.join(d, "ref.wav")
        ref_text = os.path.join(d, "ref_text.txt")
        missing = [os.path.basename(x) for x in (gpt, sovits, ref, ref_text) if not os.path.isfile(x)]
        roles[name] = {
            "name": name,
            "dir": d,
            "gpt": gpt,
            "sovits": sovits,
            "ref": ref,
            "ref_text_file": ref_text,
            "ready": not missing,
            "missing": missing,
        }
    return roles


ROLES = discover_roles()
READY_ROLES = [n for n, r in ROLES.items() if r["ready"]]
if not READY_ROLES:
    raise RuntimeError(
        "没有可用的声音模型：%s 目录下没有任何完整的角色模型（需要 <角色名>.ckpt + .pth + ref.wav + ref_text.txt）。"
        "请先在训练中心（启动训练中心-文字驱动.bat）训练并发布模型，或把模型目录复制到该路径。" % GSV_MODELS_DIR
    )

_initial_role = READY_ROLES[0]
_initial = ROLES[_initial_role]


def _read_ref_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:  # noqa: BLE001
        return ""


# 启动前把 api.py 的参数填好（默认加载第一个可用角色），再导入 GPT-SoVITS api
os.chdir(GSV_ROOT)
if GSV_ROOT not in sys.path:
    sys.path.insert(0, GSV_ROOT)
sys.argv = [
    "api.py",
    "-s", _initial["sovits"],
    "-g", _initial["gpt"],
    "-dr", _initial["ref"],
    "-dt", _read_ref_text(_initial["ref_text_file"]),
    "-dl", "zh",
    "-d", TTS_DEVICE,
    "-hb", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-hubert-base"),
    "-b", os.path.join(GSV_ROOT, "GPT_SoVITS", "pretrained_models", "chinese-roberta-wwm-ext-large"),
    "-p", str(API_PORT),
]
import api as gpt_api  # noqa: E402

_gsv_lock = threading.Lock()
_synth_lock = threading.Lock()  # 整个合成过程串行，避免并发请求干扰模型状态
_loaded_char = _initial_role
_speaker_cache = {}  # 已加载过的角色常驻内存，切换角色不再重新读盘
# 缓存策略：默认单角色（切换角色自动清理上一个并释放显存）；页面可勾选多角色缓存。
# 勾选状态持久化到 tmp\tts_cache_mode.txt，服务重启后保持用户选择。
_cache_mode_file = os.path.join(TMP_ROOT, "tts_cache_mode.txt")


def _load_multi_roles():
    try:
        with open(_cache_mode_file, encoding="utf-8") as f:
            return f.read().strip() == "1"
    except Exception:  # noqa: BLE001
        return False


_multi_roles = os.environ.get("TTS_MULTI_ROLES", "") == "1" or _load_multi_roles()


def refresh_roles():
    """训练中心发布新模型后，调用本函数即可热加载，无需重启。"""
    global ROLES, READY_ROLES
    ROLES = discover_roles()
    READY_ROLES = [n for n, r in ROLES.items() if r["ready"]]
    return ROLES


def gpt_sovits_tts(character, text, top_k, top_p, temperature, speed, sample_steps=32):
    """用 GPT-SoVITS 按角色音色合成文字语音。返回 (音频numpy, 采样率)。
    缓存策略：默认只缓存一个角色（切换角色时自动清理上一个并释放显存），
    页面勾选"缓存多个角色模型"后（_multi_roles=True）才保留多个。"""
    global _loaded_char
    info = ROLES[character]
    if not info["ready"]:
        raise RuntimeError("角色 %s 模型不完整（缺 %s）" % (character, "、".join(info["missing"])))
    ref_text = _read_ref_text(info["ref_text_file"])
    with _gsv_lock:
        if character not in _speaker_cache:
            # 单角色缓存模式：先清空旧缓存、释放显存，再加载当前角色
            if not _multi_roles and _speaker_cache:
                logger.info("单角色缓存模式：清理角色缓存 %s，加载 %s", list(_speaker_cache.keys()), character)
                _speaker_cache.clear()
                gpt_api.speaker_list.pop("default", None)
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:  # noqa: BLE001
                    pass
            logger.info("加载角色模型(首次，约1-2分钟): %s", character)
            gpt = gpt_api.get_gpt_weights(info["gpt"])
            sovits = gpt_api.get_sovits_weights(info["sovits"])
            _speaker_cache[character] = gpt_api.Speaker(name=character, gpt=gpt, sovits=sovits)
            logger.info("角色模型加载完成: %s", character)
        if gpt_api.speaker_list.get("default") is not _speaker_cache[character]:
            gpt_api.speaker_list["default"] = _speaker_cache[character]
            _loaded_char = character
        gen = gpt_api.get_tts_wav(
            ref_wav_path=info["ref"],
            prompt_text=ref_text,
            prompt_language="zh",
            text=text,
            text_language="zh",
            top_k=int(top_k), top_p=float(top_p),
            temperature=float(temperature), speed=float(speed),
            inp_refs=[], sample_steps=int(sample_steps), if_sr=False,
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
        return audio, sr


def split_text_for_tts(text, max_len=60):
    """仅对长文字分句：按句末标点切，单句超过 max_len 再硬切。短文字保持整段，保证语气连贯。"""
    import re as _re
    puncs = "。？！；…"
    parts = _re.split("([" + puncs + "])", text)
    chunks = []
    cur = ""
    for i in range(0, len(parts) - 1, 2):
        cur += parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
        if len(cur) >= 2 and (parts[i + 1] if i + 1 < len(parts) else ""):
            chunks.append(cur)
            cur = ""
    if cur or (parts and not chunks):
        chunks.append(cur)
    final = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if len(c) <= max_len:
            final.append(c)
        else:
            while len(c) > max_len:
                final.append(c[:max_len])
                c = c[max_len:]
            if c:
                final.append(c)
    return "\n".join(final)


def _clean_text_for_tts(text):
    """合成前清洗文本：去掉 GPT-SoVITS 无法处理的 markdown / URL / 邮箱 /
    代码块 / 特殊符号，保留中文、字母、数字与常用标点。
    解决“长回复含特殊内容时合成失败（500）→ 前端误回退系统语音”的问题。"""
    import re as _re
    t = str(text or "")
    t = _re.sub(r"```[\s\S]*?```", "", t)                      # 代码块
    t = _re.sub(r"`([^`]*)`", r"\1", t)                        # 行内代码
    t = _re.sub(r"^#{1,6}\s*", "", t, flags=_re.M)             # 标题 #
    t = _re.sub(r"\*\*([^*\n]+)\*\*", r"\1", t)                # **粗体**
    t = _re.sub(r"__([^_\n]+)__", r"\1", t)                    # __粗体__
    t = _re.sub(r"~~([^~\n]+)~~", r"\1", t)                    # ~~删除线~~
    t = _re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)            # [文字](链接)
    t = _re.sub(r"https?://\S+", "网址", t)                    # URL
    t = _re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "邮箱", t)        # 邮箱
    t = _re.sub(r"^[\s]*[-*+]\s+", "", t, flags=_re.M)         # - 列表项
    t = _re.sub(r"^\s*\d+[.、)]\s+", "", t, flags=_re.M)       # 1. 有序列表
    # 删除白名单之外的字符（特殊符号/emoji 等）
    t = _re.sub(
        r"[^\u4e00-\u9fffA-Za-z0-9，。！？、；：\"\"''（）《》…—·,.!?%+\s]",
        "", t,
    )
    t = _re.sub(r"\s+", " ", t).strip()
    return t


def _trim_edges(audio, sr, threshold=0.006, pad=0.08):
    """裁剪首尾静音，避免分句拼接时出现过长停顿。"""
    if len(audio) == 0:
        return audio
    frame = int(sr * 0.02)
    n = (len(audio) - frame) // frame
    if n <= 0:
        return audio
    rms = np.sqrt(np.array([
        float(np.mean(audio[i * frame:(i + 1) * frame] ** 2)) for i in range(n)
    ]))
    active = np.where(rms > threshold)[0]
    if len(active) == 0:
        return audio
    pad_s = int(pad * sr)
    start = max(0, active[0] * frame - pad_s)
    end = min(len(audio), (active[-1] + 1) * frame + pad_s)
    return audio[start:end]


def _synth_chunks(character, text, top_k, top_p, temperature, speed, sample_steps):
    """长文字分句合成，句间用交叉淡化平滑过渡；短文字整段合成保持连贯。
    合成前先清洗文本（去 markdown/URL/特殊符号），避免 GPT-SoVITS 失败。
    分句阈值 20 字：部分模型（fengyanlin/dabing 等）对 20-60 字长句整段合成会
    丢 token 漏字，分句后每句更短、合成稳定（句间用交叉淡化衔接，听感连续）。
    分句后：过短碎片句并入前句（短句易跳读漏字）、单句失败自动重试。"""
    text = _clean_text_for_tts(text)
    if not text:
        raise RuntimeError("没有可合成的文字")
    if len(text) <= 20:
        return gpt_sovits_tts(character, text, top_k, top_p, temperature, speed, sample_steps=sample_steps)
    sentences = [s for s in split_text_for_tts(text).split("\n") if s.strip()]
    if not sentences:
        raise RuntimeError("没有可合成的文字")
    # 过短碎片句（<6 字）并入前句，减少跳读漏字
    merged = []
    for s in sentences:
        if merged and len(s) < 6:
            merged[-1] += s
        else:
            merged.append(s)
    sentences = merged
    pieces = []
    sr = 32000
    for s in sentences:
        a, sr = _synth_one_retry(character, s, top_k, top_p, temperature, speed, sample_steps)
        a = _trim_edges(np.asarray(a, dtype=np.float32), sr)
        pieces.append(a)
    if not pieces:
        raise RuntimeError("合成结果为空")
    return _crossfade_join(pieces, sr), sr


def _synth_one_retry(character, s, top_k, top_p, temperature, speed, sample_steps, retries=2):
    """单句合成，失败（异常或结果过短）自动重试，最多 retries 次。"""
    last = None
    for _ in range(retries + 1):
        try:
            a, sr = gpt_sovits_tts(character, s, top_k, top_p, temperature, speed, sample_steps=sample_steps)
            if a is not None and len(a) > 0 and len(a) > int(sr * 0.2):  # 非空且不短于 0.2 秒
                return a, sr
            last = RuntimeError("单句合成结果为空或过短: %s" % s)
        except Exception as exc:  # noqa: BLE001
            last = exc
            logger.warning("单句合成失败，重试: %s -> %s", s[:20], exc)
    raise last


def _crossfade_join(pieces, sr, fade=0.12):
    """把多段音频用交叉淡化拼接：前段淡出、后段淡入重叠，听感连续不静音。"""
    n = int(sr * fade)
    if n <= 0 or len(pieces) == 1:
        return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
    out = pieces[0].astype(np.float32)
    for a in pieces[1:]:
        a = a.astype(np.float32)
        if len(out) < n or len(a) < n:
            out = np.concatenate([out, a])
            continue
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        tail = out[-n:] * (1.0 - ramp)
        head = a[:n] * ramp
        out = np.concatenate([out[:-n], tail + head, a[n:]])
    return out


# ---------------- FastAPI 服务 ----------------
from fastapi import FastAPI, Form, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, Response  # noqa: E402

app = FastAPI(title="文字驱动语音（GPT-SoVITS TTS）")

# NOTICE: 开放浏览器跨域（AIRI 数字人前端在 localhost:5173 直接调本服务）。
# 仅放开本地开发端口；如需更严可把列表换成具体 origin。不影响 TTS 合成逻辑。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8088",
        "http://localhost:8088",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>文字驱动语音</title>
<style>
body{font-family:"Microsoft YaHei",sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#222}
h1{border-bottom:2px solid #1e6fb3;padding-bottom:8px}
.card{background:#eef6fd;border:1px solid #ddd;border-radius:10px;padding:18px;margin:14px 0}
label{display:block;margin:10px 0 4px;font-weight:600}
textarea{width:100%;min-height:100px;font-size:16px;padding:8px;box-sizing:border-box}
select{padding:6px;width:200px}
button{background:#1e6fb3;color:#fff;border:none;padding:10px 26px;border-radius:6px;font-size:16px;cursor:pointer;margin-top:12px}
button:disabled{background:#aaa}
.msg{margin-top:10px;font-size:14px}
.ok{color:#27ae60}.err{color:#c0392b}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ccc;padding:6px 10px;text-align:left;font-size:14px}
</style>
</head>
<body>
<h1>文字驱动语音</h1>
<div class="card">
  <label>输入文字（最多 1000 字）</label>
  <textarea id="text" placeholder="例如：大家好，我是雷军。"></textarea>
  <label>声音角色</label>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <select id="character"></select>
    <button id="btnDel" style="background:#c0392b;margin-top:0;padding:6px 14px;font-size:13px">🗑 删除角色</button>
  </div>
  <label style="display:flex;align-items:center;gap:6px;font-weight:normal;font-size:13px">
    <input type="checkbox" id="multiCache" style="width:auto">缓存多个角色模型（默认只缓存 1 个，切换音色时自动释放上一个，省显存）
  </label>
  <label>语速：<span id="speed_v">1.0</span></label>
  <input type="range" id="speed" min="0.8" max="1.2" step="0.05" value="1.0" oninput="document.getElementById('speed_v').textContent=this.value">
  <br>
  <button id="btn">开始合成</button>
  <div id="msg" class="msg"></div>
  <div id="result" style="display:none;margin-top:10px">
    <audio id="player" controls style="width:100%"></audio>
  </div>
</div>
<div class="card">
  <h2>声音角色</h2>
  <table><tr><th>角色</th><th>状态</th></tr><tbody id="models"></tbody></table>
</div>
<script>
async function loadModels(){
  try {
    const j = await (await fetch('/models')).json();
    const sel = document.getElementById('character');
    const prev = sel.value;  // 记住用户当前选中的角色，刷新后保持，不跳回第一个
    sel.innerHTML = '';
    document.getElementById('models').innerHTML = j.models.map(m=>{
      if (m.ready){
        const o = document.createElement('option'); o.value = m.name; o.textContent = m.name; sel.appendChild(o);
        return '<tr><td>'+m.name+'</td><td class="ok">可用</td></tr>';
      }
      return '<tr><td>'+m.name+'</td><td class="err">缺文件：'+(m.missing||[]).join('、')+'</td></tr>';
    }).join('');
    if (prev && sel.querySelector('option[value="'+prev+'"]')) sel.value = prev;
    const msg = document.getElementById('msg');
    if (msg && msg.textContent.indexOf('无法连接服务') !== -1){ msg.textContent=''; msg.className='msg'; }
  } catch(e){
    // 服务未就绪：明确提示，避免误以为角色被删除
    const msg = document.getElementById('msg');
    if (msg && msg.textContent.indexOf('合成') === -1){
      msg.className='msg err';
      msg.textContent='⚠ 无法连接服务：服务可能正在启动（首次加载约 5-10 分钟）或已停止。若长时间无响应，请到文字驱动项目目录（wenziqudong）双击「一键启动文字驱动语音.bat」启动。';
    }
  }
}
document.getElementById('btn').addEventListener('click', async ()=>{
  const text = document.getElementById('text').value.trim();
  const msg = document.getElementById('msg');
  if (!text){ msg.className='msg err'; msg.textContent='请先输入文字'; return; }
  const btn = document.getElementById('btn'); btn.disabled = true;
  msg.className='msg'; msg.textContent='合成中（首次使用该角色需加载模型，请稍候）…';
  try{
    const fd = new FormData();
    fd.append('text', text);
    fd.append('character', document.getElementById('character').value);
    fd.append('speed', document.getElementById('speed').value);
    const r = await fetch('/tts', {method:'POST', body: fd});
    if (!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail || r.statusText); }
    const url = URL.createObjectURL(await r.blob());
    document.getElementById('player').src = url;
    document.getElementById('result').style.display = 'block';
    msg.className='msg ok'; msg.textContent='合成完成';
  }catch(e){
    const netErr = /Failed to fetch|NetworkError|Load failed|ECONNREFUSED|fetch failed|ERR_CONNECTION/i.test(String((e && e.message) || e));
    msg.className='msg err';
    msg.textContent = netErr
      ? '无法连接服务：服务可能正在启动（首次加载模型约 5-10 分钟）或已停止。请稍候刷新页面重试；若长时间无响应，请到文字驱动项目目录（wenziqudong）双击「一键启动文字驱动语音.bat」启动。'
      : '合成失败：'+e.message;
  }
  finally{ btn.disabled = false; }
});
document.getElementById('btnDel').addEventListener('click', async ()=>{
  const name = document.getElementById('character').value;
  const msg = document.getElementById('msg');
  if (!name){ msg.className='msg err'; msg.textContent='请先选择要删除的角色'; return; }
  if (!confirm('确定删除角色「'+name+'」？\\n\\n将永久删除本地模型文件（ckpt / pth / ref.wav / ref_text.txt），不可恢复！\\n删除后训练中心需重新训练才能找回。')) return;
  const typed = prompt('防误删：请输入角色名「'+name+'」以确认删除：');
  if (typed !== name){ msg.className='msg err'; msg.textContent='输入的角色名不一致，已取消删除'; return; }
  const fd = new FormData(); fd.append('character', name);
  try{
    const r = await fetch('/api/delete_role', {method:'POST', body: fd});
    const j = await r.json().catch(()=>({}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    msg.className='msg ok'; msg.textContent = j.message || '已删除';
    loadModels();
  }catch(e){
    msg.className='msg err'; msg.textContent='删除失败：'+e.message;
  }
});
loadModels();
// 缓存策略：默认单角色（切换时自动释放上一个）；勾选多角色缓存
(async function(){
  try{
    const j = await (await fetch('/api/cache_mode')).json();
    document.getElementById('multiCache').checked = !!j.multi;
  }catch(e){ /* 服务未就绪忽略 */ }
})();
document.getElementById('multiCache').addEventListener('change', async ()=>{
  const fd = new FormData();
  fd.append('multi', document.getElementById('multiCache').checked ? '1' : '0');
  const msg = document.getElementById('msg');
  try{
    const r = await fetch('/api/cache_mode', {method:'POST', body: fd});
    const j = await r.json().catch(()=>({}));
    if (j.message){ msg.className='msg'; msg.textContent = j.message; }
  }catch(e){
    msg.className='msg err'; msg.textContent='设置缓存模式失败：'+e.message;
  }
});
// 每 10 秒自动刷新角色列表：训练中心发布新模型后，下拉框自动出现新角色，无需手动刷新页面
setInterval(loadModels, 10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.get("/health")
def health():
    import torch
    return {
        "status": "ok",
        "service": "wenziqudong-tts",
        "port": API_PORT,
        "device": "cuda:0" if torch.cuda.is_available() else "cpu",
        "infer_device": TTS_DEVICE,
        "ready_roles": READY_ROLES,
    }


@app.get("/models")
def list_models():
    refresh_roles()
    models = []
    for name in sorted(ROLES):
        r = ROLES[name]
        models.append({
            "name": name,
            "ready": r["ready"],
            "missing": r["missing"],
        })
    return {"models": models}


@app.post("/tts")
def tts(
    text: str = Form(""),
    character: str = Form(""),
    speed: float = Form(1.0),
    top_k: int = Form(12),
    top_p: float = Form(0.9),
    temperature: float = Form(0.7),
    sample_steps: int = Form(32),
):
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    if len(text) > 1000:
        raise HTTPException(400, "text 最长 1000 字")
    if not CHARACTER_RE.match(character or ""):
        raise HTTPException(400, "character 名称不合法")
    refresh_roles()
    if character not in ROLES or not ROLES[character]["ready"]:
        raise HTTPException(404, "角色不可用: %s（可用角色见 GET /models）" % character)
    try:
        logger.info("合成文字(%d字) 角色=%s: %s", len(text), character, text[:40])
        with _synth_lock:
            audio_np, sr = _synth_chunks(
                character, text, top_k, top_p, temperature, speed, sample_steps=sample_steps)
        if len(audio_np) == 0:
            raise HTTPException(500, "合成结果为空")
        out_wav = os.path.join(TMP_ROOT, "tts_%s.wav" % uuid.uuid4().hex)
        sf.write(out_wav, audio_np, sr)
        return FileResponse(out_wav, media_type="audio/wav", filename="tts_%s.wav" % character)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("合成失败")
        raise HTTPException(500, "合成失败: %s" % exc)


@app.post("/api/free_memory")
def free_memory():
    """清空已加载的角色模型并释放显存；关闭项目（结束进程）时内存会全部释放。"""
    with _gsv_lock:
        _speaker_cache.clear()
        gpt_api.speaker_list.pop("default", None)
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
    return {"message": "已清空模型缓存并释放显存（下次合成需重新加载模型，约20秒）"}


@app.post("/api/reset")
def reset():
    """卡住时一键重置：1 秒后退出进程，由启动脚本看门狗自动重启。"""
    def _do():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_do, daemon=True).start()
    return {"message": "服务即将重置重启，约 10 秒后恢复"}


@app.get("/api/cache_status")
def cache_status():
    """查看当前角色模型缓存状态（排查缓存清理问题用）。"""
    with _gsv_lock:
        cur = gpt_api.speaker_list.get("default")
        return {
            "multi": _multi_roles,
            "cached_roles": list(_speaker_cache.keys()),
            "cache_count": len(_speaker_cache),
            "current_default": getattr(cur, "name", None) if cur is not None else None,
        }


@app.get("/api/cache_mode")
def cache_mode_get():
    """查询缓存策略：multi=True 多角色缓存 / False 单角色缓存（默认）。"""
    return {"multi": _multi_roles}


@app.post("/api/cache_mode")
def cache_mode_set(multi: str = Form("0")):
    """设置缓存策略：multi=1 多角色缓存（保留所有用过的角色）；multi=0 单角色缓存
    （切换角色时自动清理上一个并释放显存）。"""
    global _multi_roles
    _multi_roles = (multi == "1")
    try:
        with open(_cache_mode_file, "w", encoding="utf-8") as f:
            f.write("1" if _multi_roles else "0")
    except Exception:  # noqa: BLE001
        pass
    if not _multi_roles:
        # 切回单角色模式：立即清理，只保留当前正在用的角色
        with _gsv_lock:
            keep = gpt_api.speaker_list.get("default")
            keep_name = getattr(keep, "name", None) if keep is not None else None
            _speaker_cache.clear()
            if keep_name and keep is not None:
                _speaker_cache[keep_name] = keep
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
    return {"multi": _multi_roles, "message": "已开启多角色缓存（多个音色常驻，切换秒回）" if _multi_roles else "已切换为单角色缓存（切换音色时自动释放上一个）"}


@app.post("/api/delete_role")
def delete_role(character: str = Form("")):
    """真删角色：删除本地模型目录（ckpt/pth/ref.wav/ref_text.txt），不可恢复。
    同时清空该角色在内存/显存中的缓存。"""
    character = (character or "").strip()
    if not CHARACTER_RE.match(character):
        raise HTTPException(400, "角色名不合法")
    refresh_roles()
    if character not in ROLES:
        raise HTTPException(404, "角色不存在: %s" % character)
    role_dir = ROLES[character]["dir"]
    # 1) 从内存/显存缓存清除（如果该角色已加载）
    with _gsv_lock:
        _speaker_cache.pop(character, None)
        sp = gpt_api.speaker_list.get("default")
        if sp is not None and getattr(sp, "name", None) == character:
            gpt_api.speaker_list.pop("default", None)
    # 2) 删除本地模型目录
    try:
        import shutil
        shutil.rmtree(role_dir, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("删除角色目录失败: %s", role_dir)
        raise HTTPException(500, "删除失败: %s" % exc)
    # 3) 刷新角色列表 + 释放显存
    refresh_roles()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass
    logger.info("角色已删除(本地文件已移除): %s (%s)", character, role_dir)
    return {"message": "角色 %s 已删除，本地模型文件已移除（不可恢复）" % character, "deleted": character}


# ---------------- OpenAI 兼容端点（供 Open WebUI 等外部系统调用） ----------------
# OpenAI 兼容协议：
#   POST {base}/v1/audio/speech  ->  合成语音（音色 voice = 训练好的角色名）
#   GET  {base}/v1/audio/voices  ->  音色列表（Open WebUI 设置页“TTS Voice”下拉自动显示）
#   GET  {base}/v1/models        ->  角色模型列表（OpenAI 格式）
# 对话模型（duihuamoxing）内置朗读服务（8061）使用同一份代码，读它自己的 tts_service\models。


@app.post("/v1/audio/speech")
async def openai_compat_speech(request: Request):
    """OpenAI 兼容 TTS 合成。请求体 JSON：{model, input, voice, speed, ...}
    voice（或 model）即训练好的角色名；input 为要朗读的文本；返回 audio/mpeg
    （mp3）。返回 mp3 而非 wav 可以让 Open WebUI 跳过 pydub 转码，端到端
    更快（Open WebUI 的 transcode_audio_to_mp3 对 audio/mpeg 直接放行）。"""
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "请求体必须是 JSON")
    text = (payload.get("input") or "").strip()
    if not text:
        raise HTTPException(400, "input 不能为空")
    if len(text) > 1000:
        raise HTTPException(400, "text 最长 1000 字")
    character = (payload.get("voice") or payload.get("model") or "").strip()
    # light-avatar 数字人素材库（voice 前缀 avatar:）：不合成音色，
    # 画面由前端显示，音频用默认训练音色合成
    if character.startswith("avatar:"):
        character = TTS_DEFAULT_VOICE
    if not CHARACTER_RE.match(character or ""):
        raise HTTPException(400, "voice/character 名称不合法")
    refresh_roles()
    if character not in ROLES or not ROLES[character]["ready"]:
        raise HTTPException(404, "角色不可用: %s（可用角色见 GET /v1/audio/voices）" % character)
    try:
        speed = float(payload.get("speed") or 1.0)
    except (TypeError, ValueError):  # noqa: BLE001
        speed = 1.0
    # 采样参数：Open WebUI 等外部系统一般不传，用保守默认值（top_k=12/top_p=0.9/
    # temperature=0.7）。GPT-SoVITS 默认 1.0 对部分音色（如 fengyanlin）采样过激，
    # 会导致整句丢 token 漏字；保守参数对所有音色更稳。
    try:
        top_k = int(payload.get("top_k") or 12)
        top_p = float(payload.get("top_p") or 0.9)
        temperature = float(payload.get("temperature") or 0.7)
    except (TypeError, ValueError):  # noqa: BLE001
        top_k, top_p, temperature = 12, 0.9, 0.7
    try:
        logger.info("OpenAI兼容合成(%d字) 角色=%s: %s", len(text), character, text[:40])
        with _synth_lock:
            audio_np, sr = _synth_chunks(character, text, top_k, top_p, temperature, speed, sample_steps=TTS_SAMPLE_STEPS)
        if len(audio_np) == 0:
            raise HTTPException(500, "合成结果为空")
        mp3 = _wav_to_mp3(audio_np, sr)
        if mp3:
            return Response(content=mp3, media_type="audio/mpeg")
        # ffmpeg 不可用时回退 wav（Open WebUI 仍可转码，只是稍慢）
        buf = io.BytesIO()
        sf.write(buf, audio_np, sr, format="WAV")
        return Response(content=buf.getvalue(), media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI兼容合成失败")
        raise HTTPException(500, "合成失败: %s" % exc)


def _wav_to_mp3(audio_np, sr):
    """用 ffmpeg 把合成音频转成 mp3 字节；失败返回 None（调用方回退 wav）。
    优先用项目内置 ffmpeg（runtime\ffmpeg）。"""
    try:
        import subprocess
        candidates = [
            os.environ.get("FFMPEG_PATH", ""),
            os.path.join(PROJECT_ROOT, "runtime", "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(PROJECT_ROOT, "runtime", "ffmpeg", "bin", "ffmpeg"),
            "ffmpeg",
        ]
        ffmpeg = None
        for c in candidates:
            if not c:
                continue
            if c == "ffmpeg":
                # PATH 查找
                import shutil as _sh
                if _sh.which("ffmpeg"):
                    ffmpeg = "ffmpeg"
                    break
            elif os.path.isfile(c):
                ffmpeg = c
                break
        if not ffmpeg:
            return None
        buf_in = io.BytesIO()
        sf.write(buf_in, audio_np, sr, format="WAV")
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", "pipe:0",
             "-codec:a", "libmp3lame", "-b:a", "128k", "-f", "mp3", "pipe:1"],
            input=buf_in.getvalue(),
            capture_output=True,
            timeout=60,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        logger.warning("ffmpeg 转码失败 rc=%s: %s", proc.returncode, proc.stderr[:200])
    except Exception:  # noqa: BLE001
        logger.exception("mp3 转码异常，回退 wav")
    return None


@app.get("/v1/audio/voices")
def openai_compat_voices():
    """OpenAI 兼容音色列表：只返回训练好的声音角色。
    （数字人是独立功能，人物在数字人设置面板里选，不混入声音下拉。）"""
    refresh_roles()
    return {"voices": [{"id": n, "name": n} for n in sorted(ROLES) if ROLES[n]["ready"]]}


@app.get("/v1/models")
def openai_compat_models():
    """OpenAI 兼容模型列表（Open WebUI 的 TTS Model 字段可用）。"""
    refresh_roles()
    return {"data": [{"id": n, "name": n} for n in sorted(ROLES) if ROLES[n]["ready"]]}


def _startup_warmup():
    """启动后后台预加载默认音色（TTS_DEFAULT_VOICE）到缓存，避免外部调用首次请求时
    模型尚未就绪。关键：**只加载缓存、绝不切换/设置默认角色**——用户切换了哪个角色
    就用哪个，任何情况下都不会"自动切回"默认音色（用户明确要求：切换了就不要再回去）。"""
    import time as _t
    _t.sleep(2)
    try:
        role = TTS_DEFAULT_VOICE if TTS_DEFAULT_VOICE in ROLES and ROLES[TTS_DEFAULT_VOICE]["ready"] else (READY_ROLES[0] if READY_ROLES else None)
        if not role:
            return
        with _gsv_lock:
            if _speaker_cache or role in _speaker_cache:
                logger.info("已有角色在使用（%s），跳过预热，避免抢占/切回", list(_speaker_cache.keys()))
                return
            logger.info("后台预热音色模型(仅加载缓存，不切换默认): %s", role)
            gpt = gpt_api.get_gpt_weights(ROLES[role]["gpt"])
            sovits = gpt_api.get_sovits_weights(ROLES[role]["sovits"])
            _speaker_cache[role] = gpt_api.Speaker(name=role, gpt=gpt, sovits=sovits)
            # 注意：这里不设置 speaker_list["default"]，默认角色只在用户实际合成时确定
            logger.info("音色预加载完成(仅缓存): %s", role)
    except Exception:  # noqa: BLE001
        logger.exception("预热失败（不影响服务，首次合成可能稍慢）")


threading.Thread(target=_startup_warmup, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, workers=1)
