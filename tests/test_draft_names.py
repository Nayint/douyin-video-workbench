"""Named creations must keep their title across execution, recovery and revisions."""
from backend import core, dify, jobs, note_layout
from tests.test_api import client


def prepare(client, monkeypatch):
    case = core.put('case', {'title': '参考视频', 'transcript': '测试逐字稿'})
    note = core.sync_note('产品资料', 'name-test-product', '测试产品', '已确认产品事实')
    product = core.put('product', {'name': '测试产品', 'note': note, 'files': []})
    monkeypatch.setattr(dify, 'validate_inputs', lambda *args: {})
    return {'case_id': case['id'], 'product_id': product['id'], 'draft_name': '  我的新品介绍  ',
            'request_key': 'named-creation', 'mode': 'prototype'}


def assert_named(draft):
    assert draft['title'] == '我的新品介绍'
    assert '我的新品介绍--' in draft['note']['path']
    text = core.note_read(draft['note']['path'])
    assert 'title: 我的新品介绍' in text


def test_named_generation_and_revision(client, monkeypatch):
    payload = prepare(client, monkeypatch)
    # The local name is stored with the task, never guessed as a new Dify input.
    preview = client.post('/api/dify/preview', json=payload).json()
    assert 'draft_name' not in preview['inputs']
    task = client.post('/api/dify/generate', json=payload).json()
    assert task['payload']['draft_name'] == '我的新品介绍'
    monkeypatch.setattr(dify, 'upload', lambda *a: {'upload_file_id': 'fixture-file'})
    monkeypatch.setattr(dify, 'run', lambda *a: {'final_copy': '单元测试文案，不代表真实模型输出。'})
    result = jobs.work(task)
    draft = core.get(result['draft_id'], 'draft')
    assert_named(draft)
    version = client.post('/api/drafts/' + draft['id'] + '/versions', json={'content': '人工编辑的新版本'}).json()
    assert_named(version)
    assert version['parent_id'] == draft['id']
    assert '单元测试文案' in core.note_read(draft['note']['path'])
    note_layout.migrate()
    assert_named(core.get(version['id'], 'draft'))
    returned = client.get('/api/drafts').json()
    assert all(d['title'] == '我的新品介绍' for d in returned)


def test_named_recovery_is_idempotent(client, monkeypatch):
    payload = prepare(client, monkeypatch)
    task = client.post('/api/dify/generate', json=payload).json()
    jobs.task_update(task['id'], status='interrupted', run_id='existing-run')
    calls = []
    def request(mode, method, path):
        calls.append(method)
        return {'status': 'succeeded', 'outputs': {'final_copy': '测试恢复结果'}}
    monkeypatch.setattr(dify, 'request', request)
    for _ in range(2):
        response = client.post('/api/tasks/' + task['id'] + '/resume')
        assert response.status_code == 200
    assert calls == ['GET', 'GET']
    assert len(core.records('draft')) == 1
    assert_named(core.records('draft')[0])


def test_name_validation_and_legacy_fallback(client, monkeypatch):
    payload = prepare(client, monkeypatch)
    payload['draft_name'] = '字' * 201
    assert client.post('/api/dify/generate', json=payload).status_code == 422
    old = jobs.draft_version(payload['case_id'], payload['product_id'], '旧入口仍可使用')
    assert old['title'] == '原创文案 · 参考视频'
