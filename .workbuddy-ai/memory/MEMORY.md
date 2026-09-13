# wenziqudong 项目长期记忆

## 端口约定（2026-09-13 起，硬规矩）

- **本项目对外端口固定 18062，不得变动。** 对外提供接口服务，地址必须稳定可预期。
- 为什么是 18062：本机 Windows 动态端口范围是 **1024~15000**（被 Docker/WSL 改过，默认应 49152 起），
  80xx 段全在池内、会被系统当临时端口随机分配；18062 在池外，天然不会被抢占。
- 历史沿革：默认 8060 → 被 duihuamoxing 占用 → 自动漂移到 8062 → 2026-09-13 先固定 8062，
  再按用户决定改为 **18062**（一劳永逸）。
- `tts_service\choose_port.ps1` 已删除。**禁止恢复「自动挑端口」逻辑。**
- `TTS_API_PORT` 环境变量仍可覆盖，仅作逃生舱。
- 同机端口分配（互不冲突）：**wenziqudong → 18062**；duihuamoxing → 8061（备用）/ 18060（主力）。

## 依赖方（改端口时必须同步，共 3 个）

1. **`D:\xm\easy-story`** —— `config.json` 的 `tts.baseUrl`、`tts.mjs` 的 `BASE`、
   `启动语音服务.bat`、docs 两份。
2. **`D:\xm\FunnyAnimationAssitant`** —— `tools/lib-ttsapi.mjs` 的 `BASE`（可用 `TTS_API_BASE` 覆盖）、
   `tools/demo-server.py`、`tools/sync-story.mjs`、`tools/generate-studio-demo.mjs`、
   `studio/app.js`、`tools/README.md`、`项目结构说明.md`、`stories/` 两份、三个 `.bat`。
3. **`D:\xm\zhuomianchunwu\airi`（桌面宠物 AIRI）** —— 调用点不止 5 类，**全部**要改：
   - `apps/stage-web/vite.config.ts` —— vite 代理 `/tts-api` → 18062
   - `packages/stage-ui/src/stores/providers.ts` —— provider 默认 baseUrl
   - `apps/stage-web/src/pages/mine.vue` —— **TTS_BASE 硬编码（最易漏）**
   - `packages/stage-ui/src/composables/use-simple-voice.ts` —— `TTS_BASE='/tts-api'`（走代理）
   - `apps/data/local-auth-db.json` —— 浏览器本地存储快照，`wenziqudong-speech` 的 baseUrl
     ⚠️ 这是**双重转义**的 JSON 字符串（值里每个引号都写成 `\\"`），直接全局替换
     `127.0.0.1:8060` → `:18062` 子串即可；且运行中的 airi 可能把浏览器 IndexedDB 写回旧值
   - `start.bat` —— **一键启动脚本**，原本会启动 `D:\xm\duihuamoxing\文字驱动语音` 的 8060 副本
     （错配！），已改为检测 + 拉起 `D:\xm\wenziqudong\start.bat`
   - `scripts/lip-sync-train/gen_samples.py` —— `TTS_BASE` 常量（独立训练样本小工具）
   - 若干注释 + airi 自己的 DEPLOY.md
   - **教训**：airi 第一次改漏了 start.bat / gen_samples.py / local-auth-db.json 三处，
     复扫（排除 backup、限定源码目录）才揪出。改完务必复扫整个项目。

**不是依赖方（别瞎改）**：duihuamoxing 用 8061/18060 自家副本；xunlianzhongxin 是 8050 训练中心；
yijuhuakelongshengyin / tihuanshengyin 是同类 TTS **提供方**。
`aiyuelao`（Go testdata）、`aijianjishiping`/`jianjiruanji`（Shotcut vmaf）、
`renshifouhuozhe`（vocab.json）、`youxijie*`（3D 姿态/Blender）里的 8xxx 全是数字巧合。

## 项目要点

- 主服务 `tts_service\tts_api.py`（FastAPI + 网页 + OpenAI 兼容端点）；看门狗 `tts_watchdog.ps1`。
- 大件不入库：`gptsovits\GPT-SoVITS`、`runtime\`、`tts_service\models\` 音色。
- 启停脚本：纯 ASCII 英文、CRLF、无 BOM；用 `%~dp0` 定位，不硬编码盘符。
- 改代码后同步更新 README.md / DEPLOY.md / 部署方案.md；对外接口变化还要改《接口文档.md》。
- 本机安全策略：Bash/PowerShell 均无法调用 `cmd.exe` / `Start-Process` / `wmic` / `schtasks`，
  **无法代启动服务，必须用户手动双击 `start.bat`**。
  - 2026-09-13 实测：Python `subprocess` 能把 `powershell -File tts_watchdog.ps1` 拉起来（拿得到 PID），
    但看门狗内部的 `Start-Process python.exe` 仍被拦 → 日志刷 `job assign failed: ... hProcess 为空`、
    `service started (python PID=)`、`service exited (ran 0s)`，**python 根本没起来**。
  - 所以别再试图代启动；清理后要记得删掉残留的 `tts_service\tmp\tts_watchdog.pid`。
- **验证对接方是否打对端口的可行办法**：在 18062 起一个**桩 HTTP 服务**（返回 /health、/models、
  /v1/audio/speech 假 mp3），然后跑对接方的客户端看它是否请求到 18062。无需显卡、几秒出结果。
- 跨项目搜端口：`xargs` 管道遇中文路径会静默丢文件，用 Python 遍历才可靠。
- **文件编码坑**：`.bat` 是 **GBK + CRLF**，`.mjs/.json/.md/.py` 是 UTF-8。
  用 Edit 工具改 GBK 的 bat 会写坏中文 → 必须用 Python 按原编码读写。
  JS 字符串里的 `D:\\xm\\wenziqudong` 在文件里是**字面两个反斜杠**，替换串要写四个。
