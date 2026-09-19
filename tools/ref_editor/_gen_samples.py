# -*- coding: utf-8 -*-
"""一次性：生成 A/B 试听素材。跑完即删。

对每个角色合成同一句测试句，产出：
    <role>_now.wav     当前 ref_text.txt 的效果
    <role>_before.wav  已改的两个角色：改回旧值后的效果（旧 vs 新 对比）
    <role>_alt.wav     拿不准的三个角色：换成 ASR 候选文本后的效果
"""
import os
import shutil

import requests

MODELS = r"D:\xm\wenziqudong\tts_service\models"
BACKUP = os.path.join(MODELS, "_ref_backup")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
BASE = "http://127.0.0.1:18062"
TEXT = "今天天气不错，我们一起去公园走走吧，你觉得怎么样呢"

ROLES = ["ayaka", "azhong", "fengyanlin", "keai", "laolei",
         "liejun", "liuyanhua", "songwukong", "yueliang"]

# 已改的两个：备份里是旧值，当前是新值
CHANGED = ["azhong", "yueliang"]
# 拿不准的三个：ASR 给出的候选（用户听着定）
ALT = {
    "keai": "新团长他欺负我",
    "laolei": "熟悉的味道不会",
    "songwukong": "不能饿着自己下午大比较忙",
}

os.makedirs(OUT, exist_ok=True)
sess = requests.Session()
sess.trust_env = False


def synth(role, dest):
    r = sess.post(BASE + "/tts", data={"text": TEXT, "character": role}, timeout=300)
    if r.status_code != 200:
        print("  FAIL", role, r.status_code, r.text[:100])
        return False
    with open(dest, "wb") as fh:
        fh.write(r.content)
    print("  ok  %-28s %7d bytes" % (os.path.basename(dest), len(r.content)))
    return True


def ref_path(role):
    return os.path.join(MODELS, role, "ref_text.txt")


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(s)


print("=== 1) 当前状态 ===")
for r in ROLES:
    synth(r, os.path.join(OUT, r + "_now.wav"))

print("=== 2) 已改的两个：生成「改之前」===")
for r in CHANGED:
    cur = read(ref_path(r))
    old = read(os.path.join(BACKUP, r + ".ref_text.txt"))
    try:
        write(ref_path(r), old)
        synth(r, os.path.join(OUT, r + "_before.wav"))
    finally:
        write(ref_path(r), cur)
    assert read(ref_path(r)) == cur, "恢复失败！"
    print("  已恢复当前值:", cur)

print("=== 3) 拿不准的三个：生成「候选文本」===")
for r, alt in ALT.items():
    cur = read(ref_path(r))
    try:
        write(ref_path(r), alt)
        synth(r, os.path.join(OUT, r + "_alt.wav"))
    finally:
        write(ref_path(r), cur)
    assert read(ref_path(r)) == cur, "恢复失败！"
    print("  已恢复原值:", cur)

print()
print("素材目录:", OUT)
for f in sorted(os.listdir(OUT)):
    print("  ", f, os.path.getsize(os.path.join(OUT, f)))
