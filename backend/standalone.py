"""Browser workbench entry: isolated data, optional owned Ollama, no desktop app."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', choices=('127.0.0.1','0.0.0.0'), default='127.0.0.1')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--no-models', action='store_true', help='基础验收时不启动或下载模型')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--import-backup', type=Path)
    args = parser.parse_args()
    os.environ['VIRALLAB_STANDALONE'] = '1'
    if args.data_dir: os.environ['VIRALLAB_DATA'] = str(args.data_dir.expanduser().resolve())
    from . import core
    from filelock import FileLock, Timeout
    import httpx
    import uvicorn
    from .desktop_setup import initialize, import_backup
    lock = FileLock(str(core.DATA / 'workbench.lock'))
    try: lock.acquire(timeout=0)
    except Timeout: raise SystemExit('此资料库已在运行，请打开已有工作台，或选择其他资料目录')
    engine = None
    log = None
    try:
        initialize()
        if args.import_backup:
            import_backup(args.import_backup)
            print('备份导入完成；本机路径与模型配置保留。')
            return
        dist = core.ROOT / 'frontend/dist-standalone'
        os.environ['VIRALLAB_FRONTEND_DIST'] = str(dist)
        if not (dist / 'index.html').is_file(): raise SystemExit('请先运行 npm --prefix frontend run build:standalone，或运行 scripts/run_workbench.py --setup')
        with socket.socket() as check:
            try: check.bind((args.host, args.port))
            except OSError: raise SystemExit(f'端口 {args.port} 已占用；不会停止现有服务，请使用 --port 18765')
        if not args.no_models:
            base = core.local_url(core.settings()['ollama_url'])
            def ready():
                try:
                    with httpx.Client(trust_env=False, timeout=2) as client:
                        return client.get(base + '/api/tags').status_code == 200
                except httpx.HTTPError: return False
            if not ready():
                executable = shutil.which('ollama')
                if not executable:
                    candidates = [Path('/Applications/Ollama.app/Contents/Resources/ollama'),
                                  Path(os.environ.get('LOCALAPPDATA', '.')) / 'Programs/Ollama/ollama.exe']
                    executable = next((str(path) for path in candidates if path.is_file()), None)
                if not executable: raise SystemExit('未找到 Ollama。请让 Codex 按 docs/QUICKSTART.md 安装后重新运行；无需 Dify。')
                logs = core.DATA / 'logs'; logs.mkdir(exist_ok=True)
                log = (logs / 'ollama.log').open('ab')
                engine = subprocess.Popen([executable, 'serve'], stdout=log, stderr=subprocess.STDOUT,
                    env={**os.environ, 'OLLAMA_HOST': base, 'OLLAMA_NO_CLOUD': '1',
                         'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_NUM_PARALLEL': '1'})
                for _ in range(60):
                    if ready(): break
                    if engine.poll() is not None: raise SystemExit('Ollama 启动失败，请查看资料目录 logs/ollama.log')
                    time.sleep(0.5)
                else: raise SystemExit('Ollama 启动超时，请查看资料目录 logs/ollama.log')
            os.environ['VIRALLAB_AUTO_MODELS'] = '1'
        from .app import app
        url = f'http://127.0.0.1:{args.port}'
        state = core.DATA / 'workbench-runtime.json'
        state.write_text(json.dumps({'url': url, 'pid': os.getpid()})); state.chmod(0o600)
        print('工作台：' + url + '\n资料位置：' + str(core.DATA) + '\n首次使用将自动准备本地模型，进度可在网页中查看。', flush=True)
        if not args.no_browser:
            def open_when_ready():
                for _ in range(80):
                    try:
                        if httpx.get(url + '/api/health', trust_env=False, timeout=1).status_code == 200:
                            webbrowser.open(url); return
                    except httpx.HTTPError: pass
                    time.sleep(0.25)
            threading.Thread(target=open_when_ready, daemon=True).start()
        try: uvicorn.run(app, host=args.host, port=args.port, access_log=False)
        finally: state.unlink(missing_ok=True)
    finally:
        if engine is not None and engine.poll() is None:
            engine.terminate()
            try: engine.wait(timeout=5)
            except subprocess.TimeoutExpired: engine.kill(); engine.wait()
        if log: log.close()
        lock.release()


if __name__ == '__main__': main()
