# 项目约定（wenziqudong 文字驱动语音）

> 本文件随项目分发：把整个项目文件夹复制到任意电脑后，这里的约定继续生效。
> 具体项目的指令优先级高于全局约定，用户当场说的话优先级最高。

## 1. 项目概述

文字驱动语音服务（独立项目，默认端口 8060）：输入文字 → 用训练好的 GPT-SoVITS 音色模型合成语音。
只做推理；音色模型由训练方（GPT-SoVITS few-shot 训练）产出「4 件套」后，用户手动复制到
`tts_service\models\<角色名>\`，本服务目录扫描自动识别，不做训练、不接收自动推送。

## 2. 关键结构

- `tts_service\tts_api.py`：主服务（FastAPI，8060，内置网页界面 + OpenAI 兼容端点）
- `tts_service\tts_watchdog.ps1`：看门狗（服务崩溃 3 秒自动重启）
- `tts_service\models\<角色名>\`：音色模型目录（自备，目录扫描自动识别）
- `gptsovits\GPT-SoVITS\`、`runtime\`：第三方引擎/运行时，体积大不入库，见 `DEPLOY.md`
- `tests\`：自研测试脚本；`tts_service\tmp\`：运行时临时文件/日志（不入库）
- `一键启动文字驱动语音.bat` / `关闭文字驱动语音.bat`（及 `start.bat`/`stop.bat` 通用入口）

## 3. 工作方式

- 启动：双击 `start.bat` 或 `一键启动文字驱动语音.bat`（防重复双击、看门狗托管、就绪自动开浏览器）
- 服务在前台黑框窗口运行，日志实时滚动（同时写 `tts_service\tmp\tts_python.log`，stdout/stderr 已合并且由 tts_api.py 自身双写；旧 `.err` 文件已废弃）
- 停止：双击 `stop.bat` 或 `关闭文字驱动语音.bat`（先杀看门狗再杀 python，关闭后不会自动重启）；**直接关闭服务窗口亦可**——python 由 Windows Job 对象（KILL_ON_JOB_CLOSE）托管，看门狗一死内核立即终止服务，显卡/内存随之释放，不留孤儿进程
- 自检：`GET /health`、`GET /models`；`python tests\test_tts_client.py` 冒烟合成
- OpenAI 兼容端点（供 Open WebUI 等调用）：`POST /v1/audio/speech`（JSON {model, input, voice, speed} → mp3）、
  `GET /v1/audio/voices`、`GET /v1/models`
- 角色热加载：`GET /models` 会重新扫描模型目录，放入新模型目录后无需重启

## 4. 关键约定（非显而易见）

- 每个角色必须 4 个文件齐全才可用：`<名>.ckpt`、`<名>.pth`、`ref.wav`、`ref_text.txt`。
- 单角色缓存默认开启：切换音色自动释放上一个（省显存）；页面可勾选「缓存多个角色模型」。
- 参考音频选该角色清晰、有代表性的 3~10 秒人声；ref_text 必须与音频内容一字不差，否则合成跑偏。
- 默认端口 8060；推理设备/端口/引擎路径等均可用环境变量覆盖（见 DEPLOY.md 第 8 节），禁止硬编码本机路径。

## 5. 交付与文档约定

- 修改代码后同步更新 `README.md`、`DEPLOY.md`、`部署方案.md`（活文档，重复踩坑就补规则）。
- 启停脚本：纯 ASCII 英文内容、CRLF 行尾、无 BOM；用 `%~dp0` 定位项目根目录，不硬编码盘符。
- 测试产物/临时文件一律放本项目内（`tests\`、`tts_service\tmp\`），不放项目目录之外。

## 6. 禁止（Do NOT）

- 不在公开仓库提交：音色模型（ckpt/pth/ref.wav）、真人音频素材、`runtime\`、`gptsovits\`、
  `tts_service\tmp\`、测试产物音频、密钥文件（.env 等一律 `.gitignore`，勿 `git add -f` 强推）。
- 不修改训练方发布的模型文件（只读）。
- 文档与注释使用简体中文；用户当场说的话优先级最高。
---
### 关键点（2026-09-02 上传整理补充）
- tts_service/tts_api.py = 自研 FastAPI 封装（端口 8060；网页 + OpenAI 兼容 /v1/audio/speech + 看门狗），字节原样入库
- 引擎/模型/端口/设备全部可用环境变量覆盖：GSV_ROOT / GSV_MODELS_DIR / TTS_API_PORT / TTS_DEVICE
- 大件不入库：gptsovits\GPT-SoVITS(~4.6GB)、runtime\py312+ffmpeg(~9.6GB)、tts_service\models 音色(~1.9GB 真人音色)；摆位见 DEPLOY
- 原中文 bat 已重写为 ASCII/CRLF/无 BOM；一键启动文字驱动语音.bat 为兼容壳
- tests 只保留自研脚本（E:\ 路径已相对化）；调试音频/转写/QA 记录不入库
