# 抖音带货短视频工作台

本地运行的视频研究与文案创作工具。React + TypeScript 前端、FastAPI 后端、SQLite 数据库。支持导入视频、提取画面和逐字稿、分析内容、管理产品资料与创作文案。

## 安装与启动

需要 Python 3.11+、Node.js 20.19+、FFmpeg。根据功能配置 Ollama、faster-whisper 模型或自己的 Dify 工作流。

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

打开 http://127.0.0.1:8765 ，在设置中配置模型、笔记目录与服务地址。macOS 也可使用项目内的启动和停止脚本。

首次启动自动创建空数据库。默认笔记目录为 `~/Documents/ViralLabVault`；设置界面可指定自己的目录。转写模型路径需要按本机实际安装情况设置。Dify 工作流和作者写作卡需要自行配置，仓库不提供个人工作流、作者语料或账号凭据。

## 数据与发布范围

仓库发布视频工作台代码及必要界面素材。视频、截图、转写、分析结果、产品资料、创作记录和配置保存在本地 `data/` 或自行设置的存储目录，不随代码上传。`backups/` 也不上传。

发布检查说明见 [OPEN_SOURCE.md](docs/OPEN_SOURCE.md)。

项目原创代码采用 [MIT 许可证](LICENSE)，Copyright (c) 2026 许咏琪。第三方代码与素材遵循各自许可证，见随附 notices 和许可文件；MIT 不授予第三方素材权利。
