import importlib
import pytest

@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv('VIRALLAB_DATA',str(tmp_path/'data'))
    import backend.core as c
    importlib.reload(c)
    c.init_db()
    c.save_settings({'vault_path':str(tmp_path/'vault')})
    return c

def test_note_preserves_human_edit(core):
    r=core.sync_note('视频案例','abc','测试','第一版')
    path=core.contained(core.settings()['vault_path'],r['path'])
    path.write_text('人工内容')
    conflict=core.sync_note('视频案例','abc','测试','新分析')
    assert conflict['status']=='conflict'
    assert path.read_text()=='人工内容'
    assert core.contained(core.settings()['vault_path'],conflict['conflict']).exists()

def test_paths_and_service_boundary(core):
    with pytest.raises(ValueError): core.contained('/tmp/vault','../private')
    with pytest.raises(ValueError): core.local_url('https://cloud.example/v1')
    assert core.local_url('http://127.0.0.1:8081/v1').endswith('/v1')

def test_records(core):
    r=core.put('case',{'title':'真实案例','likes':None})
    core.update_record(r['id'],{'favorite':True})
    assert core.get(r['id'])['likes'] is None
    assert len(core.records('case'))==1
