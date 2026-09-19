# -*- coding: utf-8 -*-
"""配音角色校对台 —— 本地小服务，端口 18067。

做什么：把 9 个 TTS 角色的 ref_text.txt 摆到网页上，能听参考音频、
能听合成样音、能改文本并立刻重新合成对比、能一键还原备份。

用法（wenziqudong 的 runtime）：
    D:\\xm\\wenziqudong\\runtime\\py312\\python.exe tools\\ref_editor\\server.py

依赖：fastapi / uvicorn（tts_service 已有）。不依赖 requests。
前置：18062（真实 TTS 服务）要先起来，否则只能听已有素材、不能现场合成。
"""
import os
import shutil
import urllib.request
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

HERE = Path(__file__).resolve().parent
MODELS = Path(r"D:\xm\wenziqudong\tts_service\models")
BACKUP = MODELS / "_ref_backup"
SAMPLES = HERE / "samples"
TTS_BASE = "http://127.0.0.1:18062"
PORT = 18067   # 18066 被 G:\xmgousi\跳舞模型\tools\serve.py 占着，避开
DEFAULT_TEXT = "今天天气不错，我们一起去公园走走吧，你觉得怎么样呢"

ROLES = ["ayaka", "azhong", "fengyanlin", "keai", "laolei",
         "liejun", "liuyanhua", "songwukong", "yueliang"]

# 实测值（ffprobe 量的 ref.wav 时长，秒）
REF_SEC = {"ayaka": 5.38, "azhong": 6.81, "fengyanlin": 9.78, "keai": 3.02,
           "laolei": 3.08, "liejun": 3.53, "liuyanhua": 3.06,
           "songwukong": 3.76, "yueliang": 3.02}

# ASR 对 ref.wav 的识别结果（用来和标注文本对照）
ASR = {
    "ayaka": "晚上好，夜风舒畅，会是一个良宵呢。",
    "azhong": "从始至终也都没问一声泰玄圣女自己是否愿意？",
    "fengyanlin": "就是想到哪儿，说到那儿，感觉把脑子里的想法说出来挺好，虽然大部分时间都是自言自语。",
    "keai": "新团长，他欺负我。",
    "laolei": "熟悉的味道不会。",
    "liejun": "巨无霸去竞争。所以想一想，这个项目都不容易。",
    "liuyanhua": "走进新时代。",
    "songwukong": "不能饿着自己，下午大比较忙。",
    "yueliang": "现宇正是惊喜，对吧？",
}

# ASR 给出的候选（拿不准的，交给用户听了定）
ALT = {
    "keai": "新团长他欺负我",
    "laolei": "熟悉的味道不会",
    "songwukong": "不能饿着自己下午大比较忙",
}

app = FastAPI(title="配音角色校对台")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _read(p):
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _tts_up():
    try:
        with urllib.request.urlopen(TTS_BASE + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _synth(role, text):
    """调 18062 合成，返回 wav 字节。"""
    boundary = uuid.uuid4().hex
    body = b""
    for name, val in (("text", text), ("character", role)):
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n'
                 % (boundary, name)).encode("utf-8")
        body += val.encode("utf-8") + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(
        TTS_BASE + "/tts", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


@app.get("/", response_class=HTMLResponse)
def index():
    p = HERE / "index.html"
    if not p.is_file():
        return HTMLResponse("<h1>index.html 缺失</h1>", status_code=500)
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/api/roles")
def api_roles():
    out = []
    for r in ROLES:
        cur = _read(MODELS / r / "ref_text.txt")
        bak = _read(BACKUP / ("%s.ref_text.txt" % r))
        samples = sorted(f.name for f in SAMPLES.glob("%s_*.wav" % r))
        out.append({
            "role": r,
            "ref_sec": REF_SEC.get(r, 0),
            "text": cur,
            "backup": bak,
            "asr": ASR.get(r, ""),
            "alt": ALT.get(r, ""),
            "samples": samples,
            "changed": bool(bak) and cur != bak,
            "pending": r in ALT,
            "has_ref_wav": (MODELS / r / "ref.wav").is_file(),
        })
    return {"roles": out, "tts_up": _tts_up(), "default_text": DEFAULT_TEXT}


@app.post("/api/synth")
def api_synth(role: str = Form(""), text: str = Form("")):
    role = (role or "").strip()
    if role not in ROLES:
        raise HTTPException(400, "未知角色")
    text = (text or "").strip() or DEFAULT_TEXT
    if not _tts_up():
        raise HTTPException(503, "18062 未启动，先起 D:\\xm\\wenziqudong\\start.bat")
    try:
        data = _synth(role, text)
    except Exception as exc:
        raise HTTPException(502, "合成失败：%s" % exc)
    dest = SAMPLES / ("_live_%s.wav" % role)
    dest.write_bytes(data)
    return {"ok": True, "url": "/audio/samples/_live_%s.wav" % role, "bytes": len(data)}


@app.post("/api/save")
def api_save(role: str = Form(""), text: str = Form("")):
    role = (role or "").strip()
    if role not in ROLES:
        raise HTTPException(400, "未知角色")
    p = MODELS / role / "ref_text.txt"
    if p.is_file():
        shutil.copyfile(p, MODELS / role / "ref_text.prev.txt")
    p.write_text((text or "").strip(), encoding="utf-8")
    return {"ok": True, "text": _read(p)}


@app.post("/api/restore")
def api_restore(role: str = Form("")):
    role = (role or "").strip()
    if role not in ROLES:
        raise HTTPException(400, "未知角色")
    src = BACKUP / ("%s.ref_text.txt" % role)
    if not src.is_file():
        raise HTTPException(404, "没有备份")
    shutil.copyfile(src, MODELS / role / "ref_text.txt")
    return {"ok": True, "text": _read(MODELS / role / "ref_text.txt")}


@app.get("/audio/samples/{name}")
def audio_sample(name: str):
    p = SAMPLES / name
    if not p.is_file():
        raise HTTPException(404, "没有这个素材")
    return FileResponse(str(p), media_type="audio/wav")


@app.get("/audio/ref/{role}")
def audio_ref(role: str):
    p = MODELS / role / "ref.wav"
    if not p.is_file():
        raise HTTPException(404, "没有参考音频")
    return FileResponse(str(p), media_type="audio/wav")


if __name__ == "__main__":
    SAMPLES.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("  配音角色校对台")
    print("  页面   : http://127.0.0.1:%d/" % PORT)
    print("  角色库 : %s" % MODELS)
    print("  素材   : %s" % SAMPLES)
    print("  18062  : %s" % ("在线" if _tts_up() else "未启动（只能听已有素材）"))
    print("=" * 60, flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
