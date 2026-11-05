"""Model preparation must report readiness only after complete downloads."""
import importlib
import json

import httpx
import pytest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('VIRALLAB_STANDALONE', '1')
    monkeypatch.setenv('VIRALLAB_DATA', str(tmp_path / 'data'))
    from backend import core, local_setup
    importlib.reload(core); importlib.reload(local_setup)
    folder = tmp_path / 'whisper'; folder.mkdir()
    for name in local_setup.WHISPER_FILES: (folder / name).write_bytes(b'test-model-file')
    core.save_settings({'whisper_model': str(folder)})
    return local_setup


def client_for(monkeypatch, setup, handler):
    client = httpx.Client
    monkeypatch.setattr(setup.httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(handler)))


def test_existing_models_are_reused_without_pull(setup, monkeypatch):
    requests = []
    def handler(request):
        requests.append(request.method)
        return httpx.Response(200, json={'models': [{'name':'qwen3:8b'}, {'name':'qwen3-vl:8b-instruct'}]})
    client_for(monkeypatch, setup, handler)
    setup.prepare()
    assert setup.status()['phase'] == 'ready'
    assert requests == ['GET']


def test_interrupted_pull_is_not_reported_as_ready_and_can_retry(setup, monkeypatch):
    complete = False
    pulled = []
    def handler(request):
        if request.url.path.endswith('/tags'): return httpx.Response(200, json={'models': []})
        pulled.append(json.loads(request.content)['model'])
        data = b'{"status":"pulling","total":100,"completed":50}\n'
        if complete: data += b'{"status":"success"}\n'
        return httpx.Response(200, content=data)
    client_for(monkeypatch, setup, handler)
    setup.prepare()
    assert setup.status()['phase'] == 'error'
    assert '下载中断' in setup.status()['error']
    complete = True
    setup.prepare()
    assert setup.status()['phase'] == 'ready'
    assert pulled.count('qwen3:8b') == 2
