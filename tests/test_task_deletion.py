import pytest
from backend import core, jobs
from tests.test_api import client


@pytest.mark.parametrize('status', ['queued', 'running', 'failed', 'interrupted'])
def test_delete_restore_preserves_execution_and_idempotency(client, status):
    case = core.put('case', {'title': '需要保留的素材'})
    task = jobs.enqueue('analysis', case['id'], {'type': 'title'}, 'delete-test')
    jobs.task_update(task['id'], status=status, run_id='existing-remote-run')
    for _ in range(2):
        assert client.delete('/api/tasks/' + task['id']).status_code == 200
    assert not client.get('/api/tasks').json()
    assert client.get('/api/dashboard').json()['pending'] == 0
    preserved = jobs.task_get(task['id'])
    assert preserved['status'] == status
    assert preserved['run_id'] == 'existing-remote-run'
    assert core.get(case['id'])['title'] == '需要保留的素材'
    assert jobs.enqueue('analysis', case['id'], {'type': 'title'}, 'delete-test')['id'] == task['id']
    assert client.post('/api/tasks/' + task['id'] + '/restore').status_code == 200
    assert client.get('/api/tasks').json()[0]['id'] == task['id']


def test_hidden_running_task_can_finish_without_reappearing(client):
    task = jobs.enqueue('analysis', None, {}, 'finish-after-delete')
    jobs.task_update(task['id'], status='running')
    client.delete('/api/tasks/' + task['id'])
    jobs.task_update(task['id'], status='succeeded', progress=1)
    assert client.get('/api/tasks').json() == []
    assert jobs.task_get(task['id'])['status'] == 'succeeded'


def test_delete_unknown_task_is_clear_error(client):
    response = client.delete('/api/tasks/missing')
    assert response.status_code == 400
    assert response.json()['detail'] == '任务不存在'
