from pathlib import Path
import pytest
from backend import core, jobs
from tests.test_api import client


def make_product(client):
    return client.post('/api/products', json={'name': '右键删除测试产品', 'content': '应保留的产品原文'}).json()


def test_product_delete_restore_preserves_notes_versions_and_drafts(client):
    p = make_product(client)
    path = core.contained(core.settings()['vault_path'], p['note']['path'])
    original = path.read_bytes()
    attachment = Path(core.settings()['storage_path']) / 'original.txt'
    attachment.parent.mkdir(parents=True, exist_ok=True)
    attachment.write_text('附件原文')
    core.update_record(p['id'], {'files': [{'name': 'original.txt', 'path': 'original.txt', 'type': 'document'}]})
    version = core.put('product_version', {'product_id': p['id'], 'content': '分析结果'})
    draft = jobs.draft_version('case', p['id'], '已生成的文案', title='已有文案')
    for _ in range(2):
        assert client.delete('/api/products/' + p['id']).status_code == 200
    assert client.get('/api/products').json() == []
    assert core.get(p['id'], 'archived_product')['files'][0]['name'] == 'original.txt'
    assert path.read_bytes() == original
    assert attachment.read_text() == '附件原文'
    assert core.get(version['id'])['content'] == '分析结果'
    assert '已生成的文案' in client.get('/api/drafts/' + draft['id'] + '/export?format=txt').text
    assert client.post('/api/products/import').json()['imported'] == 0
    for _ in range(2):
        assert client.post('/api/products/' + p['id'] + '/restore').status_code == 200
    assert client.get('/api/products').json()[0]['id'] == p['id']
    assert path.read_bytes() == original


@pytest.mark.parametrize('kind', ['product_analysis', 'dify'])
def test_product_in_use_cannot_be_deleted_even_when_task_dismissed(client, kind):
    p = make_product(client)
    task = jobs.enqueue(kind, p['id'] if kind == 'product_analysis' else 'case',
                        {'product_id': p['id']} if kind == 'dify' else {}, 'using-product')
    jobs.task_update(task['id'], status='running', dismissed_at=core.now())
    response = client.delete('/api/products/' + p['id'])
    assert response.status_code == 400
    assert '请等待任务结束' in response.json()['detail']
    assert core.get(p['id'], 'product')


def test_delete_unknown_product_or_other_record_is_rejected(client):
    other = core.put('case', {'title': '无关素材'})
    for id in ('missing', other['id']):
        assert client.delete('/api/products/' + id).status_code == 400
        assert client.post('/api/products/' + id + '/restore').status_code == 400
    assert core.get(other['id'], 'case')
