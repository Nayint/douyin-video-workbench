"""Deployment-specific adapter for model versions in the existing local Dify.

No new service or package is installed. The Dify API container's own services
make private published versions; source workflows and API keys are preserved.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import urlsplit
from uuid import UUID
from . import core

LOCK = threading.RLock()
HELPER = Path(__file__).with_name('dify_model_helper.py')
ADAPTER_VERSION = 'model-versions-v3-product-brief'
PRODUCT_REUSE_PATCH = Path(__file__).resolve().parents[2] / 'dify/workflows/product_brief_reuse.py'


def call(payload):
    if not PRODUCT_REUSE_PATCH.is_file():
        raise ValueError('缺少 Dify 产品正文复用脚本，请恢复 dify/workflows/product_brief_reuse.py')
    docker = shutil.which('docker') or '/usr/local/bin/docker'
    try:
        result = subprocess.run([docker, 'exec', '-i', 'dify-local-api-1', 'python', '-c', PRODUCT_REUSE_PATCH.read_text() + '\n' + HELPER.read_text()],
                                input=json.dumps(payload), text=True, capture_output=True, timeout=180)
        line = next((line for line in reversed(result.stdout.splitlines()) if line.startswith('VIRALLAB_RESULT=')), '')
        parsed = json.loads(line.split('=', 1)[1]) if line else {}
        if result.returncode or not parsed.get('ok'):
            raise ValueError('Dify 模型版本准备失败（' + parsed.get('error_type', 'DockerUnavailable') + '），设置未宣称生效；原工作流保留')
        return parsed['data']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise ValueError('无法访问本机 Dify Docker 服务或准备模型超时；未切换到其他模型')


def status():
    try:
        return json.loads((core.DATA / 'dify-models.json').read_text())
    except (OSError, ValueError):
        return {}


def prepare(mode, selection, cfg=None):
    cfg = cfg or core.settings()
    parsed = urlsplit(cfg['dify_url'])
    if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.port != 8081:
        raise ValueError('当前模型同步适配本机 8081 端口的现有 Dify；此服务地址未接入模型管理')
    ollama = urlsplit(cfg['ollama_url'])
    if ollama.hostname not in ('127.0.0.1', 'localhost') or ollama.port != 11434:
        raise ValueError('Dify 模型同步使用现有 11434 端口的本机 Ollama；其他模型服务地址需另行适配')
    app_id = cfg['dify_keys'].get(mode, {}).get('app_id')
    try:
        app_id = str(UUID(app_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError('此 Dify 工作流未配置应用编号，无法核验真实生成模型')
    with LOCK:
        audit = call({'action': 'audit', 'app_id': app_id})
        target = {k: selection[k] for k in ('text_model', 'vision_model')}
        previous = status().get(mode, {})
        if (previous.get('adapter_version') == ADAPTER_VERSION and previous.get('app_id') == app_id and previous.get('source_id') == audit['source_id']
                and all(previous.get(k) == v for k, v in target.items())):
            return previous
        backup = core.DATA / 'dify-model-backups' / (app_id + '--' + audit['source_id'] + '.yml')
        if not backup.exists():
            exported = call({'action': 'backup', 'app_id': app_id})
            if exported['source_id'] != audit['source_id']:
                raise ValueError('Dify 发布版本在备份期间发生变化，请重试模型准备')
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with backup.open('x') as file:
                os.chmod(backup, 0o600)
                file.write(exported['dsl'])
        result = call({'action': 'prepare', 'app_id': app_id, 'source_id': audit['source_id'], **target})
        result.update(app_id=app_id, adapter_version=ADAPTER_VERSION, backup=str(backup.relative_to(core.DATA)), updated_at=core.now())
        saved = status()
        saved[mode] = result
        status_path = core.DATA / 'dify-models.json'
        temporary = status_path.with_suffix('.tmp')
        with temporary.open('w') as file:
            os.chmod(temporary, 0o600)
            json.dump(saved, file, ensure_ascii=False)
        temporary.replace(status_path)
        return result


def executed(mode, run_id):
    if not run_id:
        return []
    cfg = core.settings()
    app_id = str(UUID(cfg['dify_keys'][mode]['app_id']))
    return call({'action': 'run_models', 'app_id': app_id, 'run_id': str(UUID(run_id))})
