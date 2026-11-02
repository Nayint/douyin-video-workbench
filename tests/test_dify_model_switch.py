import json
import stat
import httpx
from backend import core, dify, dify_models, jobs
from backend.dify_models import prepare as real_prepare
from tests.test_api import client


def test_submitted_models_are_frozen_and_recorded(client, monkeypatch):
    case = core.put('case', {'title': '测试参考', 'transcript': '测试文案'})
    product = core.put('product', {'name': '测试产品', 'files': [], 'note': core.sync_note('产品资料', 'p', 'p', '测试资料')})
    monkeypatch.setattr(dify, 'validate_inputs', lambda *a: {})
    monkeypatch.setattr(dify, 'upload', lambda *a: {})
    payload = dict(case_id=case['id'], product_id=product['id'], request_key='frozen-models')
    response = client.post('/api/dify/generate', json=payload)
    assert response.status_code == 200
    task = response.json()
    original = task['payload']['model_selection']['text_model']
    assert 'model_selection' not in task['payload']['inputs']
    core.save_settings({'text_model': 'changed-after-submit'})
    versions = []
    def prepare(mode, selected, cfg=None):
        assert selected['text_model'] == original
        return {'workflow_id': '00000000-0000-4000-8000-000000000001', **selected}
    monkeypatch.setattr(dify_models, 'prepare', prepare)
    def run(mode, inputs, progress, ids, workflow_id):
        versions.append(workflow_id)
        ids('00000000-0000-4000-8000-000000000002', 'remote')
        return {'final_copy': '单元测试输出'}
    monkeypatch.setattr(dify, 'run', run)
    monkeypatch.setattr(dify_models, 'executed', lambda *a: [{'model': original, 'title': '测试节点'}])
    result = jobs.work(task)
    draft = core.get(result['draft_id'], 'draft')
    assert versions == ['00000000-0000-4000-8000-000000000001']
    assert draft['generation_models'][0]['model'] == original
    assert original in core.note_read(draft['note']['path'])
    payload['request_key'] = 'stale-model-preview'
    payload['expected_models'] = task['payload']['model_selection']
    refused = client.post('/api/dify/generate', json=payload)
    assert refused.status_code == 400
    assert '模型设置在预览后发生变化' in refused.json()['detail']


def test_dify_request_uses_explicit_version_endpoint(client, monkeypatch):
    version = '00000000-0000-4000-8000-000000000001'
    seen = []
    def respond(request):
        seen.append(request.url.path)
        assert 'model' not in json.loads(request.content)['inputs']
        return httpx.Response(200, text='data: '+json.dumps({'event': 'workflow_finished', 'data': {'status': 'succeeded', 'outputs': {'final_copy': '测试'}}})+'\n\n')
    monkeypatch.setattr(dify, 'client', lambda mode: httpx.Client(base_url='http://127.0.0.1:8081/v1/', transport=httpx.MockTransport(respond)))
    monkeypatch.setattr(dify, 'validate_inputs', lambda *a: {})
    assert dify.run('prototype', {}, lambda *a: None, lambda *a: None, version)['final_copy'] == '测试'
    assert seen == ['/v1/workflows/'+version+'/run']


def test_prepare_backs_up_before_creating_version_and_reuses_cache(client, monkeypatch):
    app_id = '00000000-0000-4000-8000-000000000003'
    cfg = {**core.settings(), 'dify_keys': {'prototype': {'app_id': app_id}}}
    calls = []
    def call(payload):
        calls.append(payload['action'])
        if payload['action'] == 'audit': return {'source_id': 'source', 'nodes': []}
        if payload['action'] == 'backup': return {'source_id': 'source', 'dsl': 'kind: app\n'}
        backup = core.DATA/'dify-model-backups'/f'{app_id}--source.yml'
        assert backup.read_text() == 'kind: app\n'
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        return {'workflow_id': 'snapshot', 'source_id': 'source', 'text_model': cfg['text_model'], 'vision_model': cfg['vision_model']}
    monkeypatch.setattr(dify_models, 'call', call)
    assert real_prepare('prototype', cfg, cfg)['workflow_id'] == 'snapshot'
    assert real_prepare('prototype', cfg, cfg)['workflow_id'] == 'snapshot'
    assert calls == ['audit', 'backup', 'prepare', 'audit']


def test_full_backup_includes_workflow_exports(client):
    import zipfile
    from backend.backup import create_backup
    folder = core.DATA/'dify-model-backups'
    folder.mkdir()
    (folder/'original.yml').write_text('kind: app\n')
    path = create_backup()
    try:
        with zipfile.ZipFile(path) as archive:
            assert archive.read('dify-workflows/original.yml') == b'kind: app\n'
    finally:
        path.unlink()
