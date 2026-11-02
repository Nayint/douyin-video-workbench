# 完整配置：复现作者的本地工作台

本指南对应 2026-11-02 的实际代码与运行环境。目标是复现同一界面、任务流程、模型选择、Dify 图和作者写作规则；视频、产品资料、历史分析、API Key 与学习反馈不随仓库分发。相同模型也可能产生不同文字，不能承诺逐字相同。

## 1. 先确定使用哪条链路

| 功能 | 需要的组件 |
|---|---|
| 手动案例、产品管理、文案编辑/导出 | 工作台 Python + Node |
| 上传视频、关键帧/音轨提取 | 再加 FFmpeg/FFprobe |
| 语音转写 | 再加 faster-whisper small 模型 |
| 视频/标题/产品分析 | 再加 Ollama 文字模型 |
| 图片识别、封面视觉研究 | 再加 Ollama 视觉模型 |
| 是皮皮呀作者创作 | 已安装作者规则 + 文字模型；不需要 Dify |
| 默认风格、参考案例创作 | 已分析案例 + 产品 + Dify 原型工作流 |
| 平台链接获取 | BiliNote 2.4.5；不同平台可能不可获取，本地上传可用 |
| 旧 Dify 链接工作流 | 另需两种桥接服务；工作台主创作流程不执行此路径 |

参考版本、模型 digest 与镜像 digest 在 [reference-environment.json](../config/reference-environment.json)。本轮实际验收平台为 Apple M5 Pro / 48 GiB 统一内存 / macOS + Python 3.11；Windows 原生启动脚本和不同 GPU/CPU 未验收。`qwen3.8:27b` 本机为 MLX / nvfp4，模型约 18.2 GB，视觉模型约 6.1 GB；还需给系统、Docker 和推理留内存，下载前检查机器资源。

## 2. 安装工作台

先安装 Git、Python 3.11、Node.js 20.19+、FFmpeg、Poppler（扫描 PDF）。macOS 已有 Homebrew 的用户可以运行：

```bash
brew install python@3.11 node ffmpeg poppler
git clone https://github.com/Nayint/douyin-video-workbench.git
cd douyin-video-workbench
bash scripts/bootstrap.sh
```

Linux 安装系统依赖可使用 `sudo apt-get update && sudo apt-get install -y ffmpeg poppler-utils`；Python 3.11 和 Node 需按自己的发行版准备。

脚本安装 Python/Node 依赖并构建前端，不下载大模型、不启动 Docker。若 Python 不在 PATH：

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.11 bash scripts/bootstrap.sh
```

启动服务：

```bash
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

访问 http://127.0.0.1:8765 。macOS 后续可双击项目内的「启动 ViralLab.command」和「停止 ViralLab.command」。不要将本项目直接作为公网多用户服务部署。

## 3. Ollama 与相同模型

从 [Ollama 官方下载页](https://ollama.com/download)安装并运行。作者当前版本为 0.40.12，端口 11434。

```bash
ollama pull qwen3.8:27b
ollama pull qwen3-vl:8b-instruct
ollama list
curl --noproxy '*' http://127.0.0.1:11434/api/tags
.venv/bin/python scripts/configure_local.py --text-model qwen3.8:27b --vision-model qwen3-vl:8b-instruct --check
```

工作台默认文字模型为较小的 `qwen3:8b`，所以必须执行上面的配置命令才与作者当前选择一致。若目标机器不支持当前模型的 MLX/nvfp4 格式，可自行改用支持的模型，但这属于兼容运行，不能标为相同模型复现。模型标签会更新；安装后运行 `scripts/verify_reference.py` 比对 digest。Ollama API [官方说明](https://docs.ollama.com/api/tags)。

Dify 在容器里调用宿主 Ollama，地址填 `http://host.docker.internal:11434`；工作台在宿主调用，地址为 `http://127.0.0.1:11434`。不要把两个地址混填。容器无法访问时，按 [Ollama FAQ](https://docs.ollama.com/faq)配置监听地址：macOS 可 `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"` 后退出并重开 Ollama。此设置扩大监听范围，只在可信本机网络与防火墙约束下使用；不要给路由器配置端口转发。

## 4. 转写模型与笔记目录

下载作者使用的同一模型 revision（下载约数百 MB，不含私人音频）：

```bash
.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('Systran/faster-whisper-small', revision='536b0662742c02347bc0e980a01041f333bce120', local_dir='data/models/faster-whisper-small')
PY
.venv/bin/python scripts/configure_local.py --whisper-model "$PWD/data/models/faster-whisper-small" --vault "$HOME/Documents/ViralLabVault"
```

目录必须包含 `model.bin` 等完整模型文件，工作台不会自动下载。使用自己的 Obsidian Vault 时，将 `--vault` 换成自己的目录；程序只写入其中的 `ViralLab/` 子目录。配置和所有业务数据保存在本地，首次启动为空库。[faster-whisper 官方用法](https://github.com/SYSTRAN/faster-whisper#usage)。

## 5. 安装同一作者写作规则

```bash
.venv/bin/python scripts/configure_local.py --install-author --check
```

此命令把仓库内的 `config/author-skills/pipi-copywriting/` 安装到当前用户 `~/.codex/skills/pipi-copywriting/`，并创建本地作者登记卡。不是安装 Codex 的前置要求，工作台只读取这个目录里的规则文本。已有不同版本时脚本会停止，避免覆盖。

安装后「文案创作 → 作者风格 → 是皮皮呀」，可选生活分享、直接推荐、演示答疑。此 SKILL.md 与作者本机实际运行版本一致，SHA-256 在参考清单中。原始视频、转写语料、私人索引与学习反馈不发布；SKILL 中的部分研究链接属于可选本地资料。没有这些数据，历史参考检索与学习经验不会凭空出现。规则是机制参考，不代表原作者本人或代言。

## 6. Dify 1.17.1

作者的默认参考案例生成依赖 Dify，作者卡生成不依赖 Dify。已安装 Dify 的用户先沿用已有安装，不要重复创建相同项目名。

全新机器先安装并启动 Docker Desktop，再运行：

```bash
.venv/bin/python scripts/prepare_dify.py
cd data/services/dify/docker
docker compose -p dify-local config --quiet
docker compose -p dify-local up -d
docker compose -p dify-local ps
```

脚本固定 Dify 1.17.1 的源码 commit，生成本机专用随机凭据和只绑定回环地址的端口配置；不复制作者的 `.env`、账号或数据库。它也包含本机实际使用的「空画布不能覆盖已有图」保护。需要支持 `!override` 的 Docker Compose 2.24.4+。首次访问 http://127.0.0.1:8081/install 创建自己的管理员。

在 Dify 中依次操作：

1. 「设置 → 模型供应商」安装 `langgenius/ollama`，参考版本为 1.0.3（完整插件标识在导出 DSL 中）。
2. 添加 LLM 对话模型 `qwen3.8:27b`，基础 URL 为 `http://host.docker.internal:11434`，本机 Ollama 不填 API Key。
3. 同样添加 `qwen3-vl:8b-instruct`，启用视觉能力。上下文长度可设 32768、最大输出 4096，按实际模型支持范围配置。
4. 「工作室 → 导入 DSL」选择 `deploy/dify/workflows/prototype.yml`，检查模型节点后发布。它是作者实际已发布图的无密钥导出，不是简化示例。
5. 打开该应用「访问 API」，创建自己的 API Key，并复制该应用的新 UUID（应用页面 URL 中的应用编号，不是工作流版本编号）。
6. 回到本项目根目录，执行下方命令。命令行隐藏输入 API Key，不把密钥放入 shell 历史。

```bash
.venv/bin/python scripts/configure_local.py --prototype-app-id 你的应用UUID --check
.venv/bin/python scripts/verify_reference.py
```

应用 ID 必须与 Key 属于同一个新应用，不能使用作者的旧 ID。工作台后续按冻结的模型选择创建独立工作流运行版本，不覆盖 Dify 源图。`backend/dify_model_helper.py` 使用 1.17.1 的内部服务，不能假定兼容其他版本。容器名默认 `dify-local-api-1`，自定义安装可通过环境变量 `VIRALLAB_DIFY_CONTAINER` 指定 API 容器。

工作流输入：`prototype_file`、`source_material`、`product_files`、`content_type`、`style_mode`、`platform_purpose`、`extra_requirements`；输出 `final_copy`。产品正文复用模块已包含在 `deploy/dify/product_brief_reuse.py`。改变这些字段、节点 ID 或模型供应商会破坏当前适配，不能只上传另一张同名流程图。

[对应版本 Compose](https://github.com/langgenius/dify/blob/1.17.1/docker/docker-compose.yaml) · [工作流 API](https://docs.dify.ai/api-reference/workflow-execution/execute-workflow)。

## 7. BiliNote 与旧链接工作流

BiliNote 是可选的视频链接获取服务。作者运行 2.4.5，镜像 digest 见参考清单；仓库不提供其 Cookie、账号、配置卷或缓存。

```bash
docker run -d --name bilinote --restart unless-stopped \
  -p 127.0.0.1:18080:80 \
  --add-host host.docker.internal:host-gateway \
  -v bilinote-models:/app/backend/models \
  -v bilinote-static:/app/backend/static \
  -v bilinote-config:/app/backend/config \
  -v bilinote-data:/app/backend/data \
  ghcr.io/jefferyhcool/bilinote:2.4.5
```

若对应版本标签不可获取，使用 `config/reference-environment.json` 中记录的镜像 digest。访问 http://127.0.0.1:18080 ，按 [BiliNote 官方说明](https://github.com/JefferyHcool/BiliNote)配置自己的 Ollama 地址和转写模型。先确认 BiliNote 自身能处理你有权使用的视频，再在工作台设置里填写 `http://127.0.0.1:18080`。平台限制、登录要求或网络变化可能导致链接获取失败；本地上传不依赖这一服务。

仓库也保留作者的 `deploy/dify/workflows/link.yml` 和两种桥接代码，供原 Dify 图单独恢复使用。桥接图会写入你指定的 Obsidian 文案目录，需明确设置：

```bash
export OBSIDIAN_COPY_DIR="$HOME/Documents/ViralLabVault/01-文案"
mkdir -p "$OBSIDIAN_COPY_DIR"
docker compose -f deploy/dify/compose.bridges.yaml up -d --build
```

两种桥接服务加入 `dify-local_default` 网络，分别使用 `bilinote_bridge` 和 `bilinote_opt_bridge` 别名。`prepare_dify.py` 生成的 override 已通过 `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` 仅放行这两个服务名。沿用已有安装时，在自己的 override 中为 `ssrf_proxy.environment` 添加 `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS: "bilinote_bridge bilinote_opt_bridge"`，然后在原 Dify docker 目录运行 `docker compose -p dify-local up -d ssrf_proxy`。不要关闭整体 SSRF 防护。工作台主路径不会执行旧 Dify 链接生成；仅为单独使用旧 Dify 图保留这些文件，未对新机器的该旧路径做端到端验收。

## 8. 恢复原有首页设备展示（可选）

Apple 的设备模型与纹理不随 MIT 代码授权。界面渲染代码、Three.js 与许可信息仍保留。若你拥有合法取得并使用相关资产的权限，可自行提供与本项目结构一致的：

- `frontend/public/duo/assets/iPhone_Duo_Render.usdc`
- 同目录 `textures/` 中模型引用的纹理

仓库提供与原制作流程对应的本地准备脚本。先确认你有权取得并使用该资产，在独立工具环境安装 USD 26.8，再准备：

```bash
python3.11 -m venv data/tools/usd
data/tools/usd/bin/python -m pip install usd-core==26.8
data/tools/usd/bin/python scripts/prepare_device_assets.py --download
cd frontend
npm run build
```

也可将最后一个参数换为 `--archive /你合法取得的原始模型.usdz`，避免重复下载。脚本核对原始归档哈希，按原流程设置 Landscape Pose、展平 USD 并重映射纹理路径；输出目录已存在时停止，不覆盖现有资产。资产仍被 Git 忽略，不会上传。

来源、版本与文件哈希见 `frontend/public/duo/sources.json`，第三方边界见 `frontend/public/duo/licenses/UPSTREAM_NOTICES.md`。缺少文件只影响三维展示。此脚本不授予第三方素材使用或再分发权。本轮可选 usd-core 下载受代理连接失败影响，未重新执行转换；流程来源于本机原准备脚本，不能把本轮记录视为新机器资产转换已通过。

## 9. 验证安装效果

```bash
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/configure_local.py --check
.venv/bin/python scripts/verify_reference.py
.venv/bin/python -m pytest -q tests/test_first_install.py
```

随后逐项使用：上传自己的测试视频 → 检查关键帧/逐字稿 → 选择文字/视觉分析 → 填产品资料 → 选择作者并核对预览 → 生成 → 在原创文案中编辑/导出。用默认风格时，必须先有已研究案例，并完成 Dify 配置。

只看界面可使用虚构演示库，绝不导入作者个人数据：

```bash
.venv/bin/python scripts/seed_demo.py --data-dir /tmp/virallab-demo
VIRALLAB_DATA=/tmp/virallab-demo .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

演示目录必须为空。不要与已运行的 8765 服务同时启动；可改用 18765 进行隔离预览。演示库没有真实研究结果，不用于证明模型效果。

## 常见问题

| 现象 | 检查 |
|---|---|
| Python 安装失败 | 确认 `python3.11 --version`，不要用系统 Python 3.9 |
| 模型名存在但结果不同 | 核对 digest、量化类型、Ollama 版本、采样参数及输入资料 |
| 作者列表为空 | 运行 `configure_local.py --install-author`；不要复制他人的绝对路径登记卡 |
| Dify 报缺应用编号 | 用配置脚本填写新应用 UUID 和匹配的 API Key |
| Dify 模型准备失败 | 检查容器名、Dify 1.17.1、模型供应商及宿主地址；运行 verify_reference |
| 默认风格没有案例可选 | 案例必须先在研究所完成分析；空库不会附带作者私人案例 |
| 扫描 PDF 无法提取 | 安装 Poppler：macOS `brew install poppler`，Ubuntu `sudo apt-get install poppler-utils` |
| 转写模型不完整 | 检查所选目录的 model.bin 与其他下载文件 |
| 第三方设备模型缺失 | 见第 8 节，其他页面不依赖它 |

完整既有测试及已知失败记录见 [OPEN_SOURCE.md](OPEN_SOURCE.md)。


## 交给 Codex 完成配置

可以在克隆后的项目中把下面提示词交给 Codex：

```text
请根据本仓库 docs/SETUP.md 和 config/reference-environment.json 配置完整视频工作台。
先检查已有 Python、Node、FFmpeg、Docker、Ollama、Dify 和模型，优先复用，保留现有数据。
使用仓库脚本安装依赖、安装作者规则、配置模型和新导入的 Dify 应用。
API Key 只在本机隐藏输入和保存，不输出、不提交；不要复制其他人的 settings.json。
逐项验证上传、转写、文字/视觉分析、作者生成、Dify 生成与导出。
用虚构样例测试并报告真实通过和未通过的项目，不把仅连通当成功能通过。
```
