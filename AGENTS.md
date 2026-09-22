# 项目约定（wenziqudong 文字变声音）

> 本文件随项目分发：把整个项目文件夹复制到任意电脑后，这里的约定继续生效。
> 具体项目的指令优先级高于全局约定，用户当场说的话优先级最高。

## 1. 项目概述

文字变声音服务（独立项目，固定端口 18062）：输入文字 → 用训练好的 GPT-SoVITS 音色模型合成语音。
只做推理；音色模型由训练方（GPT-SoVITS few-shot 训练）产出「4 件套」后，用户手动复制到
`tts_service\models\<角色名>\`，本服务目录扫描自动识别，不做训练、不接收自动推送。

## 2. 关键结构

- `tts_service\tts_api.py`：主服务（FastAPI，18062，内置网页界面 + OpenAI 兼容端点）
- `tts_service\tts_run.ps1`：启动窗口脚本（只把服务拉起一次；**无任何自动重启**，服务退出即彻底停止）
- `tts_service\models\<角色名>\`：音色模型目录（自备，目录扫描自动识别）
- `gptsovits\GPT-SoVITS\`、`runtime\`：第三方引擎/运行时，体积大不入库，见 `DEPLOY.md`
- `tests\`：自研测试脚本；`tts_service\tmp\`：运行时临时文件/日志（不入库）
- `一键启动文字变声音.bat` / `关闭文字变声音.bat`（及 `start.bat`/`stop.bat` 通用入口）

## 3. 工作方式

- 启动：双击 `start.bat` 或 `一键启动文字变声音.bat`（防重复双击、就绪自动开浏览器）；
  端口**固定 18062**、绝不自动漂移（对外接口地址必须稳定）；若 18062 被其他程序占用则明确报错退出，绝不杀其他项目的进程
- 服务在前台黑框窗口运行，日志实时滚动（同时写 `tts_service\tmp\tts_python.log`，stdout/stderr 已合并且由 tts_api.py 自身双写；旧 `.err` 文件已废弃）
- 停止：双击 `stop.bat` 或 `关闭文字变声音.bat`（按路径清扫本项目全部相关进程并**验证端口已释放**，关闭后绝不自动重启）；**直接关闭服务窗口亦可**——python 由 Windows Job 对象（KILL_ON_JOB_CLOSE）托管，窗口一死内核立即终止服务，显卡/内存随之释放，不留孤儿进程；tts_api.py 内另有父进程看护线程兜底；网页界面也有「⏹ 关闭服务」按钮
- **服务绝不允许自动启动/自动重启**（2026-09-20 按用户要求移除旧"看门狗"）：只有用户双击 start.bat 才启动；崩溃/资源不足导致启动失败时脚本直接报错退出，等资源空出来由用户重新双击启动，禁止恢复任何自动拉起、自动重试逻辑
- 自检：`GET /health`、`GET /models`；`python tests\test_tts_client.py` 冒烟合成
- OpenAI 兼容端点（供 Open WebUI 等调用）：`POST /v1/audio/speech`（JSON {model, input, voice, speed} → mp3）、
  `GET /v1/audio/voices`、`GET /v1/models`
- 对外接口文档：项目根目录《接口文档.md》，对接方按「查状态 /health → 查角色 /models → 配音 /v1/audio/speech」三步接入；`input`/`voice` 也接受 `text`/`character` 字段名；CORS 已放开（allow-origin: *）
- 角色热加载：`GET /models` 会重新扫描模型目录，放入新模型目录后无需重启

## 4. 关键约定（非显而易见）

- 每个角色必须 4 个文件齐全才可用：`<名>.ckpt`、`<名>.pth`、`ref.wav`、`ref_text.txt`。
- 单角色缓存默认开启：切换音色自动释放上一个（省显存）；页面可勾选「缓存多个角色模型」。
- 参考音频选该角色清晰、有代表性的 3~10 秒人声；ref_text 必须与音频内容一字不差，否则合成跑偏。
- 端口固定 18062（对外接口地址不得变动，禁止恢复自动换端口逻辑；18062 在 Windows 动态端口范围 1024~15000 之外，不会被系统随机抢占；同机 duihuamoxing 用 8061/18060）；
  推理设备/引擎路径等均可用环境变量覆盖（见 DEPLOY.md 第 8 节），禁止硬编码本机路径。
- 踩坑记录：机器装了 CUDA_PATH（如 CUDA 12.8）但与 onnxruntime-gpu 需求不匹配时，GPT-SoVITS 的 G2PW 文本前端
  （v3/v4 类模型）建 CUDA 会话直接抛异常、合成 500。已在 tts_api.py 启动时把 onnxruntime 的
  get_available_providers 过滤成 CPU（G2PW 很轻，CPU 足够），任何机器都稳，勿删该补丁。

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
- tts_service/tts_api.py = 自研 FastAPI 封装（端口 18062；网页 + OpenAI 兼容 /v1/audio/speech + 启动窗口脚本），字节原样入库
- 引擎/模型/端口/设备全部可用环境变量覆盖：GSV_ROOT / GSV_MODELS_DIR / TTS_API_PORT / TTS_DEVICE
- 大件不入库：gptsovits\GPT-SoVITS(~4.6GB)、runtime\py312+ffmpeg(~9.6GB)、tts_service\models 音色(~1.9GB 真人音色)；摆位见 DEPLOY
- 原中文 bat 已重写为 ASCII/CRLF/无 BOM；一键启动文字变声音.bat 为兼容壳
- tests 只保留自研脚本（E:\ 路径已相对化）；调试音频/转写/QA 记录不入库
