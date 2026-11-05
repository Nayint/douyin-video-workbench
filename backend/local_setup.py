"""Prepare public local models in the background; no Dify or account required."""
import threading
from pathlib import Path

import httpx
from . import core

LOCK = threading.RLock()
STATE = {'phase': 'idle', 'stage': '等待检查模型', 'progress': 0, 'error': None}
THREAD = None
WHISPER_REVISION = '536b0662742c02347bc0e980a01041f333bce120'
WHISPER_FILES = ('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt')


def update(**values):
    with LOCK: STATE.update(values)


def status():
    with LOCK:
        return {'bundled': False, 'managed': True, 'running': STATE['phase'] == 'ready', **STATE}


def prepare():
    try:
        cfg = core.settings()
        base = core.local_url(cfg['ollama_url'])
        update(phase='preparing', stage='检查本机模型服务', progress=0.02, error=None)
        with httpx.Client(trust_env=False, timeout=15) as client:
            response = client.get(base + '/api/tags'); response.raise_for_status()
            installed = {model['name'] for model in response.json().get('models', [])}
            names = list(dict.fromkeys((cfg['text_model'], cfg['vision_model'])))
            for index, name in enumerate(names):
                if name not in installed:
                    update(phase='downloading', stage='下载模型 ' + name, progress=0.05 + index * 0.3)
                    finished = False
                    with client.stream('POST', base + '/api/pull', json={'model': name, 'stream': True}, timeout=1800) as stream:
                        stream.raise_for_status()
                        for line in stream.iter_lines():
                            if not line: continue
                            import json
                            event = json.loads(line)
                            if event.get('error'): raise ValueError(event['error'])
                            finished = event.get('status') == 'success'
                            total, done = event.get('total', 0), event.get('completed', 0)
                            fraction = done / total if total else 0
                            update(stage='下载 ' + name + (' · %.1f%%' % (fraction * 100) if total else ' · ' + event.get('status', '准备中')),
                                   progress=0.05 + index * 0.3 + fraction * 0.25)
                    if not finished: raise ValueError('模型下载中断，请重试以继续下载：' + name)
                update(stage=name + ' 已准备', progress=0.3 + index * 0.3)
        current = Path(cfg['whisper_model']).expanduser()
        if not all((current / name).is_file() and (current / name).stat().st_size > 0 for name in WHISPER_FILES):
            update(phase='downloading', stage='下载中文转写模型（支持断点续传）', progress=0.75)
            from huggingface_hub import snapshot_download
            current = core.DATA / 'models/faster-whisper-small'
            snapshot_download('Systran/faster-whisper-small', revision=WHISPER_REVISION,
                              local_dir=current, allow_patterns=list(WHISPER_FILES), token=False)
            if not all((current / name).is_file() and (current / name).stat().st_size > 0 for name in WHISPER_FILES): raise ValueError('转写模型文件不完整')
            core.save_settings({'whisper_model': str(current)})
        update(phase='ready', stage='文字、视觉与转写模型已准备，可以开始创作', progress=1, error=None)
    except Exception as error:
        update(phase='error', stage='模型准备未完成', error='请检查 Ollama 是否运行、网络与磁盘空间后重试。' + ('（' + str(error)[:250] + '）'), progress=0)


def begin():
    global THREAD
    with LOCK:
        if THREAD is None or not THREAD.is_alive():
            THREAD = threading.Thread(target=prepare, daemon=True, name='local-model-setup')
            THREAD.start()
        return status()
