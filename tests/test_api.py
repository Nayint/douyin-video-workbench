import importlib
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('VIRALLAB_DATA',str(tmp_path/'data'))
    from backend import core
    importlib.reload(core);core.init_db();core.save_settings({'vault_path':str(tmp_path/'vault'),'storage_path':str(tmp_path/'media')})
    from backend.app import app
    from backend import dify_models, writing_guard
    # Existing API tests mock model boundaries. Guard behavior has its own tests.
    monkeypatch.setattr(writing_guard,'protect',lambda text,grounding,model,task_id,*a,**kw:(text,{
        'status':'passed','grounding_hash':grounding['hash'],'model':model,'version':'test-model-boundary'}))
    monkeypatch.setattr(dify_models,'prepare',lambda mode,selection,cfg=None:{'workflow_id':'00000000-0000-4000-8000-000000000001',**{k:selection[k] for k in ('text_model','vision_model')}})
    monkeypatch.setattr(dify_models,'executed',lambda *a:[])
    return TestClient(app,base_url='http://127.0.0.1:8765')

def test_local_boundary(client):
    assert client.post('/api/cases',headers={'Origin':'https://evil.example'},json={'title':'bad'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==403
    assert client.get('/media/%2e%2e/settings.json').status_code!=200

def test_manual_case_and_secret_redaction(client):
    r=client.post('/api/cases',json={'title':'测试案例','transcript':'这里是一段真实录入的测试文案。'})
    assert r.status_code==200,r.text
    id=r.json()['id'];detail=client.get('/api/cases/'+id).json()
    assert '这里是一段' in detail['transcript']
    assert detail['metrics']['likes'] is None
    assert client.patch('/api/cases/'+id,json={'favorite':True}).json()['favorite']
    assert client.get('/api/settings').json().get('dify_keys') is None

def test_idempotency_and_versioning(client):
    from backend import jobs,core
    a=jobs.enqueue('analysis',None,{'type':'title','material':{}},'fixed-request')
    b=jobs.enqueue('analysis',None,{'type':'title','material':{}},'fixed-request')
    assert a['id']==b['id']
    d=jobs.draft_version('case','product','初稿')
    newer=client.post('/api/drafts/'+d['id']+'/versions',json={'content':'人工修订'}).json()
    assert newer['id']!=d['id']
    assert newer['parent_id']==d['id']
    assert '初稿' in client.get('/api/drafts/'+d['id']+'/export?format=txt').text

def test_settings_block_cloud_and_escape(client):
    assert client.put('/api/settings',json={'ollama_url':'http://example.com'}).status_code==400
    assert client.put('/api/settings',json={'product_subdir':'../secret'}).status_code==400

def test_backup_integrity(client):
    import zipfile
    from backend.backup import create_backup
    path=create_backup()
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert 'data/virallab.sqlite3' in z.namelist()
    path.unlink()

def test_known_metrics_need_provenance(client):
    r=client.post('/api/cases',json={'title':'指标测试','metrics':{'likes':100}})
    assert r.status_code==400
    assert 'source' in r.json()['detail']
    r=client.post('/api/cases',json={'title':'指标测试','metrics':{'likes':100,'source':'人工查看公开页面','collected_at':'2026-10-15T15:00:00+08:00'}})
    assert r.status_code==200

def test_request_key_cannot_hide_changed_inputs(client):
    from backend import jobs
    jobs.enqueue('analysis',None,{'type':'title','material':{'title':'A'}},'same-key-changed')
    import pytest
    with pytest.raises(ValueError,match='参数已变化'):
        jobs.enqueue('analysis',None,{'type':'title','material':{'title':'B'}},'same-key-changed')
