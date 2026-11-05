<div align="center">

<img src="docs/images/hero.svg" alt="抖音带货短视频工作台" width="100%" />

# 抖音带货短视频工作台 · ViralLab

**下载到自己的电脑，在浏览器里研究视频、管理产品事实、写出自己的文案。**

[部署说明](docs/QUICKSTART.md) · [验收记录](docs/OPEN_SOURCE.md) · [MIT](LICENSE)

</div>

## 交给 Codex 安装

从 GitHub 下载本项目，在 Codex 中打开项目目录，发送：

```text
请根据 AGENTS.md 和 docs/QUICKSTART.md，把工作台完整部署到我的电脑并打开网页。
优先复用已有软件，安装缺少的依赖，保留已有资料和服务。
准备文字、视觉、转写模型；不需要 Dify 或在线模型密钥。
用独立虚构样例验证上传、转写、分析、产品资料、三种文案创作、保存和导出。
请直接操作，报告真实通过与未验证部分，不要只给我操作建议。
```

日常在本地浏览器使用。它是可自行部署的开源项目，不是苹果应用，也不是将私人资料上传到 GitHub 的在线服务。

## 启动方式

**Docker 备用方式（本轮镜像下载中断，尚未完成容器端到端验收）：**

```bash
git clone https://github.com/Nayint/douyin-video-workbench.git
cd douyin-video-workbench
docker compose up -d --build
```

打开 **http://127.0.0.1:8765**。首次构建和模型下载需要网络，网页会显示准备进度，可先整理资料。

**已有本机环境：**需要 Python 3.11+、Node 20.19+、FFmpeg/FFprobe、Poppler 和 Ollama。

```bash
python3.11 scripts/run_workbench.py --setup
```

下一次运行 `python3.11 scripts/run_workbench.py` 即可。Mac 优先采用本机模式使用原生推理加速；Docker 提供统一的运行环境。安装、端口调整、数据备份与故障处理见 [QUICKSTART](docs/QUICKSTART.md)。

## 可以完成的流程

**本地视频 → 关键帧与转写 → 文案、标题和封面研究 → 产品资料 → 原创文案 → 编辑、导出和反馈沉淀。**

- 本地视频和手动文案收录，保存逐字稿、研究结果与来源。
- 产品正文、图片、文档和 PDF 整理，区分已知事实与待确认信息。
- 可直接根据产品资料写作，也可选择作者风格或已研究视频的叙事架构。
- 生成后逐句核对事实，保留版本和检查记录；支持标注、修改对照和写作反馈。
- 首次使用引导、演示资料、模型自动准备和重试、备份与数据隔离。

主创作流程直接调用本地模型，不需要 Dify、Docker 内部工作流配置或作者的密钥。Docker 仅是可选部署方式。

<img src="docs/images/workbench-demo.png" alt="虚构演示资料：工作台列表" width="100%" />

## 默认模型与资料

文字分析、创作和事实核对使用 `qwen3:8b`，视觉分析使用 `qwen3-vl:8b-instruct`，语音识别使用固定版本的 `faster-whisper small`。模型首次准备后保存在使用者电脑，已有模型会复用；Ollama 模型约 11GB，另需转写模型及用户视频空间，建议至少 16GB 内存。

本机独立模式默认保存到 `data/standalone/`；Docker 模式使用独立资料卷和模型卷。作者私人视频、产品、历史文案、学习反馈、凭据、庄园和游戏均不随仓库提供。

模型会出错，转写、事实和生成结果需人工复核；同一套流程不保证与作者生成逐字相同的内容，不以互动指标承诺流量或转化。平台视频请先保存到本机后导入。

## 验证与维护

```bash
.venv-workbench/bin/python -m pytest -q tests/test_standalone.py tests/test_local_setup.py tests/test_first_install.py tests/test_api.py tests/test_products.py tests/test_media.py
```

真实 AI 验收使用独立空资料库和 `scripts/verify_local.py`；详细步骤及已知限制见 [部署说明](docs/QUICKSTART.md) 与 [验收记录](docs/OPEN_SOURCE.md)。不要把基础安装通过当作所有硬件、模型和平台路径均已通过。

旧版 Dify、BiliNote 高级接入与参考环境仍保留在 [SETUP.md](docs/SETUP.md)，不属于新用户独立模式的必需配置。

原创代码采用 [MIT](LICENSE)，Copyright © 2026 许咏琪。第三方代码、模型和素材遵循各自许可证，见 [DEPENDENCIES.md](docs/DEPENDENCIES.md)。
