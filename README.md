<div align="center">

# 🔊 文字驱动语音（GPT-SoVITS TTS）

> ⭐ **喜欢这个项目？请先点个 Star 支持一下，让更多人看到！** ⭐

![GitHub stars](https://img.shields.io/github/stars/yishui111/wenziqudong.svg?style=flat-square&color=orange)
![GitHub forks](https://img.shields.io/github/forks/yishui111/wenziqudong.svg?style=flat-square)
![GitHub repo size](https://img.shields.io/github/repo-size/yishui111/wenziqudong.svg?style=flat-square)

**输入文字 → 选择声音角色 → 用 GPT-SoVITS 音色模型合成自然语音（wav / mp3）。自带网页界面与 OpenAI 兼容 TTS 接口，可被 Open WebUI 等直接调用。**

</div>

---

## ✨ 项目简介

这是一个**自研的文字驱动语音（TTS）服务封装**（`tts_service/tts_api.py`，FastAPI，端口 8060）：
把训练好的 GPT-SoVITS 音色模型变成「复制进目录即自动识别、输入文字即可合成」的独立服务，只做**推理**，不做训练。

- **角色热加载**：音色模型按「目录扫描」自动发现（`tts_service\models\<角色名>\`），复制进来立刻可用，无需改代码、无需重启
- **面向集成**：提供 OpenAI 兼容端点（`/v1/audio/speech` 等），Open WebUI / 对话系统可直接把它当 TTS 引擎用
- **稳定工程化**：看门狗崩溃自愈、防重复双击、单/多角色缓存策略、文本自动清洗与分句拼接，长文合成也稳
- **依赖说明**：推理引擎用的是第三方开源项目 **GPT-SoVITS**（官方仓库 + 预训练基座），体积大、不随本仓库分发，见下方「大件资源下载」

> 💡 本仓库只包含**自己写的服务代码 / 测试脚本 / 文档**。引擎、运行时、音色模型等大件请按 `DEPLOY.md` 下载或自备。

## 🎯 主要功能

- ✍️ **文字转语音**：输入文字（≤1000 字，`TTS_MAX_CHARS` 可调），选声音角色，一键合成 wav，网页内自动试听、一键下载，并保留最近 10 条试听历史
- 🗣️ **多音色管理**：模型目录扫描自动识别；支持删除角色、缺文件提示；首次加载后常驻缓存秒回
- 🚀 **缓存策略可选**：默认「单角色缓存」（切换音色自动释放上一个，省显存）；页面勾选可开「多角色缓存」，当前缓存角色实时可见
- 🧰 **网页内服务维护**：一键「释放显存」、「重置服务」（卡住时重启进程，看门狗自动拉起），不用敲命令
- 🔌 **OpenAI 兼容接口**：`/v1/audio/speech`（mp3）、`/v1/audio/voices`、`/v1/models`，供 Open WebUI 等外部系统直接调用
- 🛡️ **看门狗自愈**：服务在前台黑框窗口运行、日志实时滚动；异常退出 3 秒自动重启；**关闭窗口 = 服务彻底结束，立即释放显卡与内存**（Windows Job 对象保证，不留孤儿进程）；一键启动防重复双击；stop.bat 一键停止
- ✂️ **长文本稳合成**：自动清洗 markdown/URL/特殊符号，20 字阈值分句 + 交叉淡化拼接，减少漏字跳读；无标点长文、末尾无标点的句子也不会丢字；合成音频内存直出，不在磁盘堆临时文件

## 🗂️ 目录结构

```
wenziqudong/
├── tts_service/
│   ├── tts_api.py            # 主服务（FastAPI，端口 8060，内置网页界面）
│   ├── tts_watchdog.ps1      # 看门狗：启动 python、崩溃 3 秒自动重启
│   └── models/<角色名>/       # 音色模型（4 件套：ckpt/pth/ref.wav/ref_text.txt，自备）
├── tests/                    # 自研测试脚本（TTS 冒烟、换角色、官方直测对比等）
├── gptsovits/GPT-SoVITS/     # 第三方推理引擎（自行下载，见下方大件表）
├── runtime/                  # Python 3.12 + ffmpeg（自行准备，见大件表）
├── start.bat                 # 通用启动入口（等价双击「一键启动文字驱动语音.bat」）
├── stop.bat                  # 通用停止入口
├── 一键启动文字驱动语音.bat     # 原版一键启动（看门狗托管、自动开浏览器）
├── 关闭文字驱动语音.bat         # 原版一键停止
├── DEPLOY.md                 # 新电脑完整部署步骤（大件下载/摆放、从零安装）
├── 部署方案.md                 # 原部署笔记（浓缩版）
├── requirements.txt          # 本服务直接依赖
└── README.md                 # 本文件
```

## 🚀 快速开始（拉到新电脑即可部署）

### 环境要求

- 操作系统：Windows 10/11（启停脚本为 .bat；Linux/macOS 可手动 `python tts_service\tts_api.py` 方式运行）
- 运行时：Python 3.10–3.12（推荐 3.12）；NVIDIA 显卡（推理建议 ≥6GB 显存；无 GPU 可设 `TTS_DEVICE=cpu` 慢速运行）
- 硬盘：引擎 + 运行时 + 音色模型约 15GB（均不随仓库分发）

### 1. 克隆

```bash
git clone https://github.com/yishui111/wenziqudong.git
cd wenziqudong
```

### 2. 准备大件（引擎 / 运行时 / 音色模型）

本仓库**不包含**推理引擎与模型，请按 [DEPLOY.md](DEPLOY.md) 的「资源下载与摆放」准备：
`gptsovits\GPT-SoVITS\`（引擎+预训练基座）、`runtime\py312\`（Python 3.12）、`runtime\ffmpeg\`，
并把音色模型 4 件套放入 `tts_service\models\<角色名>\`。

### 3. 启动

```bash
# Windows：双击 start.bat（等价：双击「一键启动文字驱动语音.bat」）
start.bat
```

> 首次启动需加载 torch / 预训练模型，约 **5–10 分钟**就绪（看门狗日志在 `tts_service\tmp\`）；就绪后脚本会自动打开浏览器。

### 4. 验证

浏览器打开 http://127.0.0.1:8060/ ，选角色、输文字、点「开始合成」，能听到语音即部署成功。

## 📥 大件资源下载（引擎 / 运行时 / 模型）

| 资源 | 用途 | 下载地址 / 获取方式 | 摆放位置 |
| ---- | ---- | ---- | ---- |
| GPT-SoVITS 推理引擎 | 推理引擎（api.py 及工具链，第三方 MIT 开源） | https://github.com/RVC-Boss/GPT-SoVITS （clone 或 Release 包） | `gptsovits\GPT-SoVITS\` |
| 预训练基座（chinese-hubert-base、chinese-roberta-wwm-ext-large 等） | 推理必需 | 引擎 README 内提供的下载地址（HuggingFace `lj1995/GPT-SoVITS` 等，国内可用镜像），官方整合包亦自带 | `gptsovits\GPT-SoVITS\GPT_SoVITS\pretrained_models\` |
| Python 3.12 运行时（含 torch 等） | 运行服务 | ① 有旧版自包含包则整目录拷贝；② python.org 装 3.12 后把安装目录拷为 `runtime\py312`（完整含 Lib/Scripts） | `runtime\py312\` |
| ffmpeg / ffprobe | OpenAI 端点输出 mp3（可选，缺了自动回退 wav） | https://ffmpeg.org 或引擎整合包自带 | `runtime\ffmpeg\bin\` |
| 音色模型 4 件套 | 每个声音角色（`<名>.ckpt` + `<名>.pth` + `ref.wav` + `ref_text.txt`） | 用 GPT-SoVITS 官方 WebUI 训练 few-shot 音色后获得（本仓库不含任何真人音色模型） | `tts_service\models\<角色名>\` |

> 详细步骤（含「从零 pip 安装、不用 bat」的替代方案）见 [DEPLOY.md](DEPLOY.md)。

## 🔌 接口速览（默认端口 8060）

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 网页界面（输入文字 → 合成语音） |
| `/tts` | POST | `text` + `character` + 可选 `speed/top_k/top_p/temperature/sample_steps` → wav |
| `/models` | GET | 角色列表（含 ready / 缺文件状态，热刷新） |
| `/health` | GET | 健康检查 |
| `/v1/audio/speech` | POST | **OpenAI 兼容 TTS**：JSON `{model, input, voice, speed}` → mp3，`voice` 即角色名 |
| `/v1/audio/voices` | GET | OpenAI 兼容音色列表（Open WebUI 的 TTS Voice 下拉自动显示） |
| `/v1/models` | GET | OpenAI 兼容角色模型列表 |
| `/api/delete_role` | POST | 删除角色（真删本地模型目录，防误删双确认） |
| `/api/cache_mode` | GET/POST | 查询 / 设置缓存策略（`multi=1` 多角色常驻） |
| `/api/cache_status` | GET | 查看显存中已缓存的角色模型 |
| `/api/free_memory` | POST | 清空角色模型缓存并释放显存 |
| `/api/reset` | POST | 服务卡住时一键重置（退出进程，看门狗 3 秒自动拉起） |

```bash
# 网页端用法
curl -X POST -F "text=大家好，我是雷军。" -F "character=liejun" http://127.0.0.1:8060/tts -o out.wav
# OpenAI 兼容用法（Open WebUI 等）
curl -X POST -H "Content-Type: application/json" -d "{\"model\":\"liejun\",\"input\":\"大家好，我是雷军。\",\"voice\":\"liejun\"}" http://127.0.0.1:8060/v1/audio/speech -o out.mp3
```

## ❓ 常见问题（FAQ）

- **Q：双击启动没反应 / 页面打不开？** A：首次加载 torch 与模型约需 5–10 分钟，期间 `/health` 不通属正常；服务与看门狗日志在 `tts_service\tmp\`（`tts_python.log` / `tts_watchdog.log`），可查看是否缺引擎/模型（先按 DEPLOY.md 摆好 `gptsovits\GPT-SoVITS` 与音色模型）。
- **Q：下拉框没有角色 / 角色显示「缺文件」？** A：每个角色目录必须 4 件齐全（`<名>.ckpt`、`<名>.pth`、`ref.wav`、`ref_text.txt`），目录放进 `tts_service\models\` 后 `GET /models` 即热刷新，无需重启。
- **Q：合成漏字 / 跳读？** A：多为参考音频问题：`ref.wav` 建议 3–10 秒干净人声，`ref_text.txt` 必须与音频内容一字不差。本服务已默认保守采样参数（top_k 12 / top_p 0.9 / temperature 0.7）+ 20 字分句，可大幅缓解。
- **Q：`Failed to fetch`？** A：服务未就绪或已停止。等就绪后刷新页面；或到项目目录双击「一键启动文字驱动语音.bat」。
- **Q：想换 GPU/CPU？** A：启动前 `set TTS_DEVICE=cpu` 再双击启动脚本（默认 cuda，需显卡）；CPU 不吃显存但合成稍慢。

## ⚠️ 注意事项

- 本仓库**不含**任何真人音色模型与训练数据，请勿上传他人声音克隆产物到公开仓库（肖像/声音权属风险）；
- 音色模型 `*.ckpt / *.pth / ref.wav` 等已被 `.gitignore` 忽略，勿用 `git add -f` 强推；
- 单角色模型约 230MB、加载 1–2 分钟；合成时 GPU 显存约 3–5GB，与其他大显存任务建议错开；
- 文字超过上限（默认 1000 字，可用环境变量 `TTS_MAX_CHARS` 调整）会被拒绝，请分段合成；
- 本仓库仅供学习交流使用，请勿用于违法违规用途。

## 📄 许可证

MIT License（引擎 GPT-SoVITS 亦为 MIT，版权归其原作者；如仓库内另带 LICENSE 则以仓库内为准）

## 🙏 支持与致谢

如果这个项目帮到了你，**请点亮右上角的 ⭐ Star**，你的支持是我持续更新的最大动力！
