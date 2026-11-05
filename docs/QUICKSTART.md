> 当前实测通过的是 macOS 本机安装与真实 AI 全流程。Docker 备用方案本轮遇到依赖下载失败和镜像传输中断，尚未完成端到端验收；Windows/Linux 也未在实体设备上验收。请让 Codex 优先使用本机方式。

# 下载后交给 Codex 部署

目标：从 GitHub 下载项目，在自己的电脑启动浏览器工作台。数据、模型和生成内容保存在本机；日常创作不需要 Dify、在线模型账号或 API Key。

## 推荐：让 Codex 完成安装

在 Codex 中打开下载的项目目录，发送：

```text
请根据 AGENTS.md 和 docs/QUICKSTART.md，把这个工作台完整部署在我的电脑并打开网页。
先检查并复用已有软件，安装缺少的依赖，保留我的已有数据与服务。
优先采用本机模式，以使用本机推理加速；若环境不适合，再使用 Docker。
完成首次文字、视觉和转写模型准备，检查实际进度；不要让我自己逐条执行命令。
用独立虚构资料验证上传、转写、分析、产品管理、自然口语/作者/参考架构写作、保存和导出。
报告实际通过与未验证部分。不要把服务连通当作 AI 流程已通过。
```

## 本机模式

需要 Python 3.11+、Node.js 20.19+、FFmpeg/FFprobe、Poppler 和 Ollama。Mac 已有 Homebrew 时，Codex 可执行：

```bash
brew install python@3.11 node ffmpeg poppler ollama
python3.11 scripts/run_workbench.py --setup
```

安装程序创建 `.venv-workbench/`、安装锁定的 Python 依赖、构建独立网页；启动已有或新安装的 Ollama，然后启动工作台并打开浏览器。下一次运行无需 `--setup`：

```bash
python3.11 scripts/run_workbench.py
```

若端口 8765 已占用，保留原服务，改用：

```bash
python3.11 scripts/run_workbench.py --port 18765
```

Linux 先准备同样的软件；Debian/Ubuntu 的媒体工具可用 `sudo apt-get install ffmpeg poppler-utils`。Python、Node、Ollama 按各自官方安装方式准备。Windows 可由 Codex 安装相同组件并用 `py -3.11 scripts/run_workbench.py --setup`；Windows 原生路径尚未完成整机验收，环境不合适时选择 Docker。

## Docker 模式

已安装并启动 Docker Desktop（或 Linux Docker Engine + Compose）后：

```bash
docker compose up -d --build
```

打开 **http://127.0.0.1:8765**。仅需 Docker，不要求宿主安装 Python、Node、FFmpeg、Ollama 或 Dify。首次构建与模型下载需要网络；网页会显示模型准备进度，失败后在系统设置点击“检查并准备模型”重试。

```bash
docker compose ps
docker compose logs --tail 100 workbench
docker compose stop
docker compose start
```

默认端口可通过 `VIRALLAB_PORT` 环境变量调整。工作台与模型分别保存在 Compose 的 `workspace`、`models` 持久卷，停止容器不会清空资料。

Docker 在 Mac 上不使用原生 Metal 加速；Mac 优先使用本机模式。模型推理速度与内存、处理器及加速支持有关。

## 第一次打开

页面打开后会自动准备：

- 文字分析、写文案和事实核对：`qwen3:8b`。
- 图片和封面分析：`qwen3-vl:8b-instruct`。
- 中文转写：固定版本的 `faster-whisper small`。

两个 Ollama 模型约 11GB，转写模型数百 MB。已有模型会复用；首次下载耗时取决于网络，需要留出模型与用户视频的空间，建议至少 16GB 内存。准备期间可以整理资料，AI 任务等待模型就绪后执行。

先选择演示资料熟悉页面，或直接导入自己的本地视频。平台视频先保存到电脑后导入。没有发布文案、话题或封面时，只分析有依据的部分并显示跳过原因。

写文案可以只选择产品，也可选择作者风格或已研究视频架构。生成后逐句核对产品事实，通过后保存；仍需人工复核模型的识别和判断。

## 数据与备份

本机模式默认目录为项目 `data/standalone/`，包括数据库、媒体、笔记、作者规则、模型和 `backups/`。原工作台的 `data/settings.json` 与原始资料不会自动复制进来。

可在系统设置创建并下载备份。更换资料库可以指定 `--data-dir`。导入旧工作台 ZIP 备份时，先停止目标服务，并使用空资料库：

```bash
python3.11 scripts/run_workbench.py --data-dir /你的空资料目录 --import-backup /你的备份.zip
python3.11 scripts/run_workbench.py --data-dir /你的空资料目录
```

导入保留当前电脑路径与配置，不导入旧电脑的模型密钥；原备份保留。Docker 导入和跨目录迁移交给 Codex 根据实际卷处理，先备份再操作。

## 检查和验收

```bash
.venv-workbench/bin/python -m pytest -q tests/test_standalone.py tests/test_local_setup.py tests/test_first_install.py tests/test_api.py tests/test_products.py tests/test_media.py
```

真实 AI 验收要另开一个空资料库，以免混入自己的业务数据。启动后运行：

```bash
.venv-workbench/bin/python scripts/verify_local.py --url http://127.0.0.1:18765 --output data/acceptance-result
```

加 `--video /你的测试视频.mp4` 可验证真实上传、转写、文字和视觉分析；不提供视频时，用脚本生成的手动文案验证分析和三种写作路径。输出目录保留验收报告和生成文案。

安装错误先检查版本、磁盘空间和网络。模型准备状态在 `/api/setup/status`；缺少 Ollama 时请让 Codex 安装并启动。不要为排错覆盖个人设置或改用作者的私有目录。

旧 Dify 和 BiliNote 的高级接入资料仍保留在 SETUP.md；新独立模式的主创作路径不依赖它们。当前是单用户本地工具，默认只对本机开放。
