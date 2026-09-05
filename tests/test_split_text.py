# -*- coding: utf-8 -*-
"""分句 / 文本清洗逻辑回归测试（不依赖服务，不加载引擎）。

从 tts_api.py 源码里提取纯函数直接执行，验证：
    1. split_text_for_tts 不丢字（历史 bug：末尾没句号的最后一句被丢、
       整段无标点的长文返回空导致合成 500）
    2. _clean_text_for_tts 保留中文弯引号、去除 URL/markdown/emoji

用法：python tests\\test_split_text.py（用项目 runtime 或任意 Python 3 均可）
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "tts_service", "tts_api.py")


def _extract_funcs(names):
    """从 tts_api.py 源码中抠出指定 def 的源码块并 exec（这些函数只依赖 re）。"""
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    ns = {"re": re}
    for name in names:
        m = re.search(r"^def %s\(.*?(?=^def |^# -{5,}|^@|\Z)" % name, src, re.S | re.M)
        if not m:
            print("FAIL: 未在 tts_api.py 中找到函数 %s" % name)
            sys.exit(1)
        exec(m.group(0), ns)  # noqa: S102
    return ns


def main():
    ns = _extract_funcs(["split_text_for_tts", "_clean_text_for_tts"])
    split = ns["split_text_for_tts"]
    clean = ns["_clean_text_for_tts"]
    fails = []

    def check(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail and not cond else ""))
        if not cond:
            fails.append(name)

    # --- 分句：不丢字（把所有分句拼回去，去掉标点差异后必须等于原文） ---
    def no_loss(t):
        parts = split(t)
        joined = "".join(p.strip() for p in parts)
        return joined == t.strip()

    cases = {
        "整段无标点长文": "大家好欢迎收看本次直播今天我们聊聊人工智能的发展历程以及它未来可能出现的变化趋势",
        "末尾无句号": "你好。世界",
        "第二句无尾标点": "第一句话在这里。第二句话也在这里，说完了",
        "正常多句": "第一句话讲完了。第二句也讲完了！最后再来一句？",
        "带问号叹号": "真的吗？不可能吧！太离谱了…",
        "单句超长硬切": "这是一个特别长的句子没有任何标点" * 5,
        "句子短碎片": "好。行。都听你的。就这么定了。",
    }
    for name, t in cases.items():
        check("分句不丢字: " + name, no_loss(t), "分句结果: %r" % split(t))

    # 长度上限：单句超长必须被硬切到都不超过 max_len
    long_parts = split("这是一个特别长的句子没有任何标点" * 5, max_len=50)
    check("硬切长度上限", all(len(p) <= 50 for p in long_parts) and len(long_parts) > 1)

    # 历史 bug 定向回归：无标点长文不能返回空（旧版返回空 -> 合成 500）
    check("无标点长文非空", len(split(cases["整段无标点长文"])) >= 1)

    # --- 清洗：弯引号保留、URL/markdown/emoji 去除 ---
    check("弯引号保留", clean("他说“你好”然后走了") == "他说“你好”然后走了", repr(clean("他说“你好”然后走了")))
    check("URL 替换", "http" not in clean("详情看 https://example.com/a?b=1 谢谢"))
    check("markdown 去除", "**加粗**" not in clean("**加粗**标题") and "#" not in clean("## 标题"))
    check("emoji 去除", clean("你好😊世界") == "你好世界", repr(clean("你好😊世界")))
    check("纯符号清空", clean("😊🤞 ### $$$") == "", repr(clean("😊🤞 ### $$$")))

    print()
    if fails:
        print("共 %d 项失败: %s" % (len(fails), "、".join(fails)))
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
