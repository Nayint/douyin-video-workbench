"""Check local prerequisites without starting jobs or reading private configuration."""
import importlib.util
import shutil
import sys
from pathlib import Path


def main():
    checks = [('Python >= 3.11', sys.version_info >= (3, 11)),
              ('FFmpeg', bool(shutil.which('ffmpeg'))),
              ('FFprobe', bool(shutil.which('ffprobe')))]
    pdf_renderer = shutil.which('pdftoppm') or (Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm').is_file()
    checks.append(('Poppler / pdftoppm (scanned PDF)', bool(pdf_renderer)))
    for name in ('fastapi', 'uvicorn', 'httpx', 'multipart', 'PIL', 'numpy', 'faster_whisper'):
        checks.append((name, importlib.util.find_spec(name) is not None))
    for name, ok in checks:
        print(f'{"OK" if ok else "MISSING"}: {name}')
    print('Ollama、转写模型、Dify 和作者卡按需配置；本检查不代表这些外部功能已通过验收。')
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
