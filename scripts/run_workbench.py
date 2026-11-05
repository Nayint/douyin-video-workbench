"""Cross-platform install/start command; only the Python standard library is needed."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true', help='安装依赖并构建网页，保留已有资料')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--no-models', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--import-backup', type=Path)
    args = parser.parse_args()
    if sys.version_info < (3, 11): raise SystemExit('请让 Codex 安装 Python 3.11 或以上版本，或选择 Docker 启动')
    directory = ROOT / '.venv-workbench'
    python = directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if args.setup:
        required = ('node', 'npm', 'ffmpeg', 'ffprobe', 'pdftoppm')
        missing = [name for name in required if not shutil.which(name)]
        if missing: raise SystemExit('缺少：' + ', '.join(missing) + '。请让 Codex 按 docs/QUICKSTART.md 安装；也可使用 Docker 模式。')
        if not python.is_file(): subprocess.run([sys.executable, '-m', 'venv', str(directory)], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.lock')], cwd=ROOT, check=True)
        npm = shutil.which('npm')
        subprocess.run([npm, 'ci'], cwd=ROOT / 'frontend', check=True)
        subprocess.run([npm, 'run', 'build:standalone'], cwd=ROOT / 'frontend', check=True)
    if not python.is_file(): raise SystemExit('首次运行请加 --setup；完整说明见 docs/QUICKSTART.md')
    command = [str(python), '-m', 'backend.standalone', '--port', str(args.port)]
    for name in ('no_models', 'no_browser'):
        if getattr(args, name): command.append('--' + name.replace('_', '-'))
    if args.data_dir: command += ['--data-dir', str(args.data_dir)]
    if args.import_backup: command += ['--import-backup', str(args.import_backup)]
    raise SystemExit(subprocess.call(command, cwd=ROOT))


if __name__ == '__main__': main()
