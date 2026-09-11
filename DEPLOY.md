
## 🚀 换电脑部署（保证可用）

> **方式 A（推荐 · 100% 保证）**：用 U 盘 / 网盘把「原项目整份文件夹」（含全部大件）复制到新电脑 → 双击 `start.bat` 即可。
>
> **方式 B（代码装配）**：`git clone` 本仓库 → 双击 `assemble.bat` 预检大件 → 按提示补齐缺失项（下载地址见下文/README）→ 双击 `start.bat`。

> 说明：引擎、模型、镜像、运行时等大件体积超过 GitHub 单文件 100MB 上限，**不随仓库分发**；本仓库承载全部自研代码与装配指引，"方式 A"是换机部署最稳路径，"方式 B"适合需要重新下载大件的场景。
# 文字驱动语音（wenziqudong）· 部署方案（DEPLOY）

> 目标：在一台新电脑上，把本仓库**部署成可用的 GPT-SoVITS 文字驱动 TTS 服务**（端口 8060）。
> 本仓库只含**自研代码/测试/文档**；引擎、运行时、音色模型均为**大件，需自行下载或从旧环境拷贝**（下方有清单）。
> 每次修改代码后同步更新本文件与 README.md。

## 1. 项目是什么

自研 FastAPI 封装（`tts_service\tts_api.py`，端口 8060）：输入文字 → 用 GPT-SoVITS 音色模型合成语音。
只做推理；音色模型按目录扫描自动识别，复制进 `tts_service\models\` 即生效。
代码通过**相对路径 + 环境变量**定位引擎与模型（无任何盘符硬编码），放到任意位置均可运行。

## 2. 环境要求

| 项 | 要求 |
| --- | --- |
| 操作系统 | Windows 10/11（`start.bat`/看门狗为 Windows 生态；也可手动用 Python 直接跑，见 6.2） |
| Python | 3.10–3.12（推荐 3.12） |
| 显卡 | NVIDIA，显存建议 ≥6GB（无 GPU 可 `TTS_DEVICE=cpu`，合成慢） |
| 磁盘 | 引擎+运行时+音色模型约 15GB |
| 其它 | 显卡驱动已装好（CUDA 版 torch 需对应驱动） |

## 3. 最终目录约定（部署完成后长这样）

```
<任意位置>\wenziqudong\            （本仓库代码）
├─ tts_service\
│   ├─ tts_api.py                  主服务（FastAPI，8060）
│   ├─ tts_watchdog.ps1            看门狗（崩溃 3 秒自动重启；日志/pid 写 tmp\）
│   └─ models\<角色名>\              音色模型 4 件套（自备，见第 5 节）
├─ tests\                          测试脚本（可选）
├─ gptsovits\GPT-SoVITS\           官方引擎（含 GPT_SoVITS\pretrained_models\ 基座）【需下载/拷贝】
├─ runtime\
│   ├─ py312\python.exe            完整 Python 3.12 环境（含 torch）【需下载/拷贝】
│   └─ ffmpeg\bin\ffmpeg.exe       ffmpeg/ffprobe 【需下载/拷贝】
├─ start.bat / stop.bat            通用启停入口
├─ 一键启动文字驱动语音.bat / 关闭文字驱动语音.bat   原版启停脚本
├─ README.md / DEPLOY.md / 部署方案.md
└─ requirements.txt
```

## 4. 资源下载与摆放（核心！）

| 资源 | 用途 | 获取方式 | 摆放位置 |
| --- | --- | --- | --- |
| GPT-SoVITS 引擎 | 推理引擎（api.py） | `git clone https://github.com/RVC-Boss/GPT-SoVITS` 或下载 Release 包（第三方 MIT 开源，版权归其作者） | `gptsovits\GPT-SoVITS\` |
| 预训练基座 | 推理必需 | 引擎 README 中给出的下载地址：HuggingFace `lj1995/GPT-SoVITS`、`hfl/chinese-roberta-wwm-ext-large` 等（国内可用 hf-mirror / ModelScope 镜像）；官方 Windows 整合包亦自带 | `gptsovits\GPT-SoVITS\GPT_SoVITS\pretrained_models\`（chinese-hubert-base、chinese-roberta-wwm-ext-large 等目录） |
| Python 3.12 运行时 | 运行服务 | 方式 A：从你已有的可运行自包含包**整目录拷贝** `runtime\`；方式 B：python.org 安装 3.12 → 装好依赖（第 6.1 节）→ 把**整个安装目录**拷为 `runtime\py312` | `runtime\py312\`（顶层要有 python.exe） |
| ffmpeg / ffprobe | `/v1/audio/speech` 输出 mp3（可选，缺了自动回退 wav） | https://ffmpeg.org 下载，或引擎整合包自带 | `runtime\ffmpeg\bin\`（不想要 mp3 可不放，wav 合成不依赖 ffmpeg） |
| NLTK 英文标注资源 | 文本含英文时的断句（可选） | 运行 `python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng', download_dir=r'<项目>\runtime\py312\nltk_data')"`，或从旧环境拷贝 `nltk_data\` | `runtime\py312\nltk_data\` |
| 音色模型 4 件套 | 每个声音角色 | 用 GPT-SoVITS 官方 WebUI 训练 few-shot 音色后获得（本仓库不含任何真人音色） | `tts_service\models\<角色名>\` |

> **有旧版自包含包最省事**：把旧 `wenziqudong` 文件夹里的 `gptsovits\`、`runtime\`、`tts_service\models\` 三个目录整体拷进克隆的仓库即可，代码零修改直接跑。

## 5. 音色模型约定（关键）

每个角色是一个目录，必须 **4 件齐全**才可用：

| 文件 | 用途 |
| --- | --- |
| `<角色名>.ckpt` | GPT 权重（文本 → 语义） |
| `<角色名>.pth` | SoVITS 权重（语义 → 语音） |
| `ref.wav` | 参考音频（该角色 3–10 秒干净人声） |
| `ref_text.txt` | 参考音频对应的文字（UTF-8，必须与音频一字不差） |

- 目录放进 `tts_service\models\` 后自动识别（`GET /models` 时热刷新，无需重启）；缺文件的角色显示「缺文件」，不进入合成下拉框。
- `ref.wav` 过长（>10 秒）或 `ref_text.txt` 与音频不符，会明显拉低合成质量（漏字/跳读），务必自查。

## 6. 启动/停止

### 6.1 方式一：标准布局 + 一键脚本（推荐）

前提：第 4 节的目录都已摆好（尤其 `runtime\py312\python.exe` 与 `gptsovits\GPT-SoVITS`）。

```bat
start.bat        :: 或双击「一键启动文字驱动语音.bat」
```

- 脚本防重复双击：已运行 → 提示退出；正在启动（看门狗存活）→ 提示退出；只有确认没在跑才启动。
- 看门狗在**前台控制台窗口**运行：服务日志实时滚动显示在该窗口（同时写入 `tts_service\tmp\tts_python.log`）；python 异常退出 **3 秒自动重启**（连续 3 次 30 秒内快速退出则看门狗自停，防死循环）；python 被 Windows Job 对象托管，**直接关闭该窗口 = 看门狗 + 服务一起结束，显卡/内存立即释放**（不留孤儿进程）。
- 首次加载 torch/模型约 **5–10 分钟**，就绪后脚本自动打开 http://127.0.0.1:8060/ 。
- 停止：`stop.bat`（或双击「关闭文字驱动语音.bat」）——先杀看门狗再杀 python 并兜底清理 8060 占用，**关闭后不会自动重启**。
- 端口/设备可用环境变量覆盖（在启动前设置，看门狗会继承）：

```bat
set TTS_DEVICE=cpu          :: 默认 cuda（需显卡）；cpu 不吃显存
set TTS_DEFAULT_VOICE=xxx   :: 默认预热音色（默认取第一个可用角色）
set TTS_API_PORT=8060       :: 默认 8060
set GSV_ROOT=D:\path\to\GPT-SoVITS   :: 引擎不在 gptsovits\GPT-SoVITS 时指定
```

### 6.2 方式二：从零 pip 安装、不用看门狗（无 runtime 目录时）

```bash
# 1) 装 Python 3.10–3.12（python.org）
# 2) 装引擎与依赖：
git clone https://github.com/RVC-Boss/GPT-SoVITS gptsovits/GPT-SoVITS
pip install -r gptsovits/GPT-SoVITS/requirements.txt     # 含 torch/torchaudio 等；GPU 版请按 PyTorch 官网 CUDA 命令安装
pip install -r requirements.txt                          # 本服务直接依赖
# 3) ffmpeg 加入 PATH（可选，仅 mp3 输出需要；也可设 FFMPEG_PATH 指向 exe）
# 4) 模型 4 件套放 tts_service/models/<角色名>/
# 5) 启动（无看门狗，崩溃不会自愈；生产建议配合 supervisor/计划任务）：
set TTS_DEVICE=cuda
python tts_service\tts_api.py
# 6) 浏览器访问 http://127.0.0.1:8060/
```

> 方式二下代码仍按相对路径找引擎（默认 `gptsovits\GPT-SoVITS`），找不到就用 `GSV_ROOT`/`GSV_MODELS_DIR` 环境变量指向已有引擎/模型目录。

## 7. 接口与自检

> 📄 对外对接文档在项目根目录 [接口文档.md](接口文档.md)（面向调用方：查状态 / 查角色 / 配音三接口 + 示例 + 错误处理），本表为速查。

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 网页界面 |
| `/tts` | POST | `text`+`character`+可选 `speed/top_k/top_p/temperature/sample_steps` → wav（内存直出，不落盘） |
| `/models` | GET | 角色列表（热刷新） |
| `/health` | GET | 健康检查（status/device/ready_roles/max_chars） |
| `/v1/audio/speech` | POST | OpenAI 兼容 TTS：JSON `{model, input, voice, speed}` → mp3（voice=角色名；`input`/`voice` 也接受 `text`/`character` 写法） |
| `/v1/audio/voices` | GET | OpenAI 兼容音色列表 |
| `/v1/models` | GET | OpenAI 兼容模型列表 |
| `/api/delete_role` | POST | 删除角色（Form: character，真删本地模型目录） |
| `/api/cache_mode` | GET/POST | 缓存策略查询/设置（multi=1/0，持久化到 tmp\tts_cache_mode.txt） |
| `/api/cache_status` | GET | 查看显存中已缓存的角色模型 |
| `/api/free_memory` | POST | 清空角色模型缓存并释放显存 |
| `/api/reset` | POST | 服务卡住时一键重置（退出进程，看门狗自动拉起） |

```bash
curl -X POST -F "text=大家好，我是雷军。" -F "character=liejun" http://127.0.0.1:8060/tts -o out.wav
curl -X POST -H "Content-Type: application/json" -d "{\"model\":\"liejun\",\"input\":\"大家好，我是雷军。\",\"voice\":\"liejun\"}" http://127.0.0.1:8060/v1/audio/speech -o out.mp3
```

自检命令：`GET /health` 正常 → `GET /models` 列出角色 → `POST /tts` 冒烟合成 wav 可播放。
测试脚本：`python tests\test_tts_client.py --character <角色名>`；`pwsh -File tests\换角色复现测试.ps1`（逐个角色加载合成）；`python tests\test_split_text.py`（分句/清洗逻辑回归，不依赖服务）。

## 8. 常用环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `TTS_DEVICE` | `cuda` | 推理设备：`cuda`/`cpu` |
| `TTS_DEFAULT_VOICE` | 第一个可用角色 | 启动后后台预热的音色 |
| `TTS_API_PORT` | `8060` | 服务端口 |
| `GSV_ROOT` | `<仓库>\gptsovits\GPT-SoVITS` | 引擎根目录 |
| `GSV_MODELS_DIR` | `<仓库>\tts_service\models` | 音色模型目录 |
| `TTS_MULTI_ROLES` | 空 | `1` = 启动即多角色缓存 |
| `TTS_SAMPLE_STEPS` | `64` | GPT 采样步数（32 更快、偶发跳读；网页与 OpenAI 端点共用） |
| `TTS_MAX_CHARS` | `1000` | 单次合成字数上限（长文本请分段，或调大此值） |
| `TTS_TMP_ROOT` | `<仓库>\tts_service\tmp` | 临时输出/日志目录 |
| `FFMPEG_PATH` | 空 | 指向 ffmpeg.exe 的绝对路径（mp3 输出用） |

## 9. 常见问题排查

- **双击没反应 / 服务起不来**：先查 `tts_service\tmp\tts_python.log`（stdout/stderr 已合并写入）与 `tts_watchdog.log`。常见：`gptsovits\GPT-SoVITS` 或 `runtime\py312\python.exe` 不存在、8060 被占用、没放音色模型（会直接报「没有可用的声音模型」）。
- **首次启动要等多久**：加载 torch/预训练模型约 5–10 分钟，期间 `/health` 不通属正常。
- **页面报「Failed to fetch」**：服务正在启动/刚重启，等就绪后刷新；或服务已停，重新双击启动脚本。
- **换角色每次都要重新加载 1–2 分钟**：每个角色是独立模型（约 230MB），首次使用加载后常驻缓存；服务重启清空缓存属正常。多个音色频繁切换可在页面勾选「缓存多个角色模型」。
- **英文混排报 `Resource 'averaged_perceptron_tagger_eng' not found`**：按第 4 节补装 NLTK 资源。
- **合成漏字/跳读**：优先检查该角色 `ref.wav` 时长（3–10 秒）与 `ref_text.txt` 是否一致；本服务默认已用保守采样参数 + 20 字分句。
- **无 GPU 也想跑**：`set TTS_DEVICE=cpu` 后启动（不吃显存，合成稍慢）。
- **端口冲突**：8060 被其他程序占用时，start.bat 自动改用 8062~8069 中第一个空闲端口（记入 `tts_service\tmp\port.txt`，stop.bat 自动跟随；8060 空出来后下次启动自动回到 8060）。也可 `set TTS_API_PORT=xxxx` 手动指定；本副本只会清理自己启动的进程，不会动其他项目的服务。
- **页面点「重置服务」被拒绝**：说明服务当前不是看门狗托管的（如手动 python 启动、看门狗已死），直接重置会无法自愈。按提示双击 `stop.bat` 再 `start.bat`（start.bat 启动时也会对这种状态打印 WARNING）。
- **启动时报 CUDA out of memory / MemoryError**：显卡或系统内存被其他 AI 程序（LLM、ComfyUI、同机其他 TTS 等）暂时占满。看门狗会每 60 秒自动重试，等资源空出来即自动启动成功；也可先关掉部分程序。

## 10. 更新约定

- 修改代码后：同步更新本文件、`部署方案.md`、README.md；
- 新增环境变量/接口时，更新第 7、8 节表格；
- 不要在仓库内提交：音色模型、`runtime\`、`gptsovits\`、`tts_service\tmp\`、测试产物音频（已由 `.gitignore` 覆盖，勿 `-f` 强推）。
