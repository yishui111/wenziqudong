# -*- coding: utf-8 -*-
"""缓存模式 / 调度顺序 实测台 —— 本地小服务，端口 18068。

回答两个问题：
  ① 单角色缓存（multi=0）切一次音色到底亏多少？
  ② 按时间顺序合成 vs 按角色分组合成，切换次数差多少？

用法：
    D:\\xm\\wenziqudong\\runtime\\py312\\python.exe tools\\cache_lab\\server.py
前置：18062（GPT-SoVITS）必须先起来。
注意：本页会真的去改 18062 的全局缓存模式（写 tts_cache_mode.txt），
      页面顶部有开关，测完记得切回你要的模式。
"""
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TTS_BASE = "http://127.0.0.1:18062"
PORT = 18068

ROLES = ["ayaka", "azhong", "fengyanlin", "keai", "laolei",
         "liejun", "liuyanhua", "songwukong", "yueliang"]

# 默认台词：模拟一段真实的多角色对白，按时间顺序交错（故意最坏情况）
DEFAULT_SEGS = [
    {"role": "azhong", "text": "你怎么来了，这里不安全"},
    {"role": "keai", "text": "我来看看你，不放心"},
    {"role": "azhong", "text": "快走，他们马上就到"},
    {"role": "laolei", "text": "老雷我可不怕他们"},
    {"role": "yueliang", "text": "月亮出来了，正好赶路"},
    {"role": "keai", "text": "真的好漂亮啊"},
    {"role": "laolei", "text": "别看了，正事要紧"},
    {"role": "azhong", "text": "前面就是城门"},
    {"role": "yueliang", "text": "守备看起来很严"},
    {"role": "keai", "text": "那我们怎么办"},
    {"role": "laolei", "text": "交给我就行"},
    {"role": "azhong", "text": "好，听我口令行动"},
]

app = FastAPI(title="缓存模式实测台")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _up():
    try:
        with urllib.request.urlopen(TTS_BASE + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _get(path, timeout=20):
    with urllib.request.urlopen(TTS_BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _form(path, fields, timeout=300):
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n'
                 % (b, k)).encode("utf-8")
        body += str(v).encode("utf-8") + b"\r\n"
    body += ("--%s--\r\n" % b).encode("utf-8")
    req = urllib.request.Request(
        TTS_BASE + path, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % b})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _synth(role, text):
    return _form("/tts", {"text": text, "character": role})


def _set_mode(multi: bool):
    return _form("/api/cache_mode", {"multi": "1" if multi else "0"}, 60)


@app.get("/", response_class=HTMLResponse)
def index():
    p = HERE / "index.html"
    if not p.is_file():
        return HTMLResponse("<h1>index.html 缺失</h1>", status_code=500)
    return HTMLResponse(p.read_text(encoding="utf-8"))


@app.get("/api/state")
def state():
    st = {"tts_up": _up(), "roles": ROLES, "segs": DEFAULT_SEGS}
    if st["tts_up"]:
        try:
            st.update(_get("/api/cache_status"))
            st["multi"] = _get("/api/cache_mode").get("multi", False)
        except Exception as exc:  # noqa: BLE001
            st["err"] = str(exc)
    return st


@app.post("/api/mode")
def mode(multi: str = Form("0")):
    if not _up():
        raise HTTPException(503, "18062 未启动")
    _set_mode(multi == "1")
    return _get("/api/cache_status")


@app.post("/api/run")
def run(multi: str = Form("0"), segs: str = Form("")):
    """按给定顺序跑一轮合成，返回每段耗时。segs = JSON 字符串。"""
    if not _up():
        raise HTTPException(503, "18062 未启动")
    try:
        items = json.loads(segs) if segs else DEFAULT_SEGS
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "台词解析失败：%s" % exc)
    bad = [i for i in items if i.get("role") not in ROLES]
    if bad:
        raise HTTPException(400, "未知角色：%s" % ",".join(i["role"] for i in bad))

    tag = "m1" if multi == "1" else "m0"
    _set_mode(multi == "1")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    prev = None
    switches = 0
    t_all = time.time()
    for i, it in enumerate(items):
        if prev is not None and it["role"] != prev:
            switches += 1
        prev = it["role"]
        t0 = time.time()
        try:
            data = _synth(it["role"], it["text"])
            err = ""
        except Exception as exc:  # noqa: BLE001
            data, err = b"", str(exc)
        dt = time.time() - t0
        name = ""
        if data:
            name = "%s_%02d_%s.wav" % (tag, i, it["role"])
            (OUT / name).write_bytes(data)
        rows.append({"i": i + 1, "role": it["role"], "text": it["text"],
                     "sec": round(dt, 2), "switched": i > 0 and items[i - 1]["role"] != it["role"],
                     "bytes": len(data), "err": err, "url": ("/audio/" + name) if name else ""})
    total = round(time.time() - t_all, 2)
    ok = [r for r in rows if not r["err"]]
    return {"multi": multi == "1", "total": total, "switches": switches,
            "avg": round(sum(r["sec"] for r in ok) / len(ok), 2) if ok else 0,
            "rows": rows}


@app.post("/api/plan")
def plan(segs: str = Form("")):
    """纯计算：按时间顺序 vs 按角色分组，切换次数差多少（不合成）。"""
    try:
        items = json.loads(segs) if segs else DEFAULT_SEGS
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "台词解析失败：%s" % exc)

    def cnt(seq):
        c, prev = 0, None
        for it in seq:
            if prev is not None and it["role"] != prev:
                c += 1
            prev = it["role"]
        return c

    grouped, seen = [], []
    for it in items:
        seen.append(it["role"])
    order, done = [], set()
    for r in seen:
        if r not in done:
            done.add(r)
            order.append(r)
    for r in order:
        grouped += [it for it in items if it["role"] == r]
    return {"time_order": {"switches": cnt(items),
                           "seq": [i["role"] for i in items]},
            "grouped": {"switches": cnt(grouped),
                        "seq": [i["role"] for i in grouped]},
            "roles_n": len(order)}


@app.get("/audio/{name}")
def audio(name: str):
    p = OUT / name
    if not p.is_file():
        raise HTTPException(404, "没有这个音频")
    return FileResponse(str(p), media_type="audio/wav")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("  缓存模式 / 调度顺序 实测台")
    print("  页面   : http://127.0.0.1:%d/" % PORT)
    print("  18062  : %s" % ("在线" if _up() else "未启动 —— 先跑 start.bat"))
    print("=" * 60, flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
