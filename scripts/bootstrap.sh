#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,11), "Requires Python >=3.11"'
command -v node >/dev/null
command -v npm >/dev/null
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/check_environment.py
(cd frontend && npm ci && npm run build)
printf '\n安装完成。配置模型及工作流见 docs/SETUP.md。启动：\n.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765\n'
