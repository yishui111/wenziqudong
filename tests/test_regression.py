# -*- coding: utf-8 -*-
"""整体回归：对运行中的服务做全端点测试。用法：
    python tests/test_regression.py [base_url]   # 默认 http://127.0.0.1:18062
"""
import sys

import requests

B = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18062"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name + (("  " + str(extra)) if extra and not cond else ""))
    ok, fail = ok + (1 if cond else 0), fail + (0 if cond else 1)


h = requests.get(B + "/health", timeout=10).json()
check("health 服务标识", h.get("service") == "wenziqudong-tts", h.get("service"))
check("health cuda", h.get("infer_device") == "cuda", h.get("infer_device"))
m = requests.get(B + "/models", timeout=10).json()
check("models 8 个角色", len(m.get("models", [])) == 8, len(m.get("models", [])))
r = requests.post(B + "/tts", data={"text": "长文本回归测试。" * 30, "character": "azhong"}, timeout=600)
check("长文本(210字)", r.status_code == 200 and len(r.content) > 100000, (r.status_code, len(r.content)))
r = requests.post(B + "/tts", data={"text": "你好。末尾没有句号也要完整读出来", "character": "azhong"}, timeout=600)
check("无尾标点不丢句", r.status_code == 200)
r = requests.post(B + "/tts", data={"text": "他说“你好”然后访问 https://a.com/x", "character": "azhong"}, timeout=600)
check("弯引号保留+URL清洗", r.status_code == 200)
check("空文本 400", requests.post(B + "/tts", data={"text": "", "character": "azhong"}, timeout=10).status_code == 400)
check("非法角色名 400", requests.post(B + "/tts", data={"text": "hi", "character": "a/b"}, timeout=10).status_code == 400)
check("不存在角色 404", requests.post(B + "/tts", data={"text": "hi", "character": "nobody"}, timeout=10).status_code == 404)
r = requests.post(B + "/v1/audio/speech", json={"model": "azhong", "input": "OpenAI 兼容接口回归。", "voice": "azhong"}, timeout=600)
check("OpenAI speech mp3", r.status_code == 200 and r.headers.get("content-type") == "audio/mpeg", r.headers.get("content-type"))
check("voices 8 个", len(requests.get(B + "/v1/audio/voices", timeout=10).json().get("voices", [])) == 8)
check("v1 models 8 个", len(requests.get(B + "/v1/models", timeout=10).json().get("data", [])) == 8)
r = requests.get(B + "/api/cache_status", timeout=10).json()
check("cache_status 有缓存", r.get("cache_count", 0) >= 1, r)
check("开多角色缓存", requests.post(B + "/api/cache_mode", data={"multi": "1"}, timeout=10).json()["multi"] is True)
check("回单角色缓存", requests.post(B + "/api/cache_mode", data={"multi": "0"}, timeout=10).json()["multi"] is False)
page = requests.get(B + "/", timeout=10).text
check("页面关键元素", all(k in page for k in ["btnFree", "btnReset", "btnDl", "wzd_tts_state", "合成历史"]))
check("释放显存接口", "释放" in requests.post(B + "/api/free_memory", timeout=60).json().get("message", ""))
print()
print("通过 %d / 失败 %d" % (ok, fail))
sys.exit(1 if fail else 0)
