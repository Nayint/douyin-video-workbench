from backend import core, jobs
from tests.test_api import client


def test_delete_restore_draft_preserves_note_versions_and_filming(client):
    case = core.put('case', {'title': '参考案例'})
    product = core.put('product', {'name': '产品'})
    original = jobs.draft_version(case['id'], product['id'], '原稿必须保留', title='我的文案')
    newer = jobs.draft_version(case['id'], product['id'], '另一个版本', parent_id=original['id'])
    client.patch('/api/drafts/' + original['id'] + '/filming', json={'filmed': True})
    path = core.contained(core.settings()['vault_path'], original['note']['path'])
    before = path.read_bytes()
    for _ in range(2):
        assert client.delete('/api/drafts/' + original['id']).status_code == 200
    assert [d['id'] for d in client.get('/api/drafts').json()] == [newer['id']]
    dashboard = client.get('/api/dashboard').json()
    assert dashboard['drafts_total'] == 1
    assert all(d['id'] != original['id'] for d in dashboard['drafts'])
    assert path.read_bytes() == before
    assert core.get(newer['id'])['parent_id'] == original['id']
    assert core.get(case['id'], 'case') and core.get(product['id'], 'product')
    for _ in range(2):
        assert client.post('/api/drafts/' + original['id'] + '/restore').status_code == 200
    restored = next(d for d in client.get('/api/drafts').json() if d['id'] == original['id'])
    assert restored['filmed'] is True
    assert restored['title'] == '我的文案'
    assert path.read_bytes() == before


def test_remote_result_recovery_does_not_resurrect_deleted_card(client):
    task = jobs.enqueue('dify', 'case', {'draft_name': '不应重新出现'}, 'deleted-draft-task')
    original = jobs.draft_version('case', 'product', '已生成结果', task_id=task['id'])
    client.delete('/api/drafts/' + original['id'])
    recovered = jobs.draft_version('case', 'product', '重复恢复结果', task_id=task['id'])
    assert recovered['id'] == original['id']
    assert len(core.records('draft')) == 1
    assert client.get('/api/drafts').json() == []


def test_wrong_record_or_unknown_id_cannot_be_deleted_or_restored(client):
    other = core.put('product', {'name': '不能误删的产品'})
    for id in ('missing', other['id']):
        assert client.delete('/api/drafts/' + id).status_code == 400
        assert client.post('/api/drafts/' + id + '/restore').status_code == 400
    assert not core.get(other['id']).get('deleted_at')
