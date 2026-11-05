"""Browser first-run/import contracts, isolated from the author's actual library."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def isolated(tmp_path, code):
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
        env={**os.environ, 'VIRALLAB_STANDALONE': '1', 'VIRALLAB_DATA': str(tmp_path / 'data'),
             'HOME': str(tmp_path / 'home'), 'TEST_ROOT': str(tmp_path)},
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def test_standalone_first_run_and_demo_are_self_contained(tmp_path):
    isolated(tmp_path, r'''
from pathlib import Path
from fastapi.testclient import TestClient
from backend import core, author_profiles
from backend.desktop_setup import initialize
initialize()
core.save_settings({'ollama_url':'http://127.0.0.1:1'})
from backend.app import app
with TestClient(app, base_url='http://127.0.0.1:19231') as client:
    status=client.get('/api/setup/status').json()
    assert status['enabled'] and not status['completed'] and status['empty']
    assert status['authors']==['是皮皮呀']
    assert not status['ollama'] and not status['whisper']
    assert author_profiles.catalog()[0]['source_count']==0
    assert Path(core.settings()['vault_path']).is_relative_to(core.DATA)
    assert author_profiles.SKILLS_ROOT.is_relative_to(core.DATA)
    assert not (Path.home()/'.codex').exists()
    assert client.post('/api/setup/complete',headers={'Origin':'https://evil.example'},json={'demo':True}).status_code==403
    response=client.post('/api/setup/complete',json={'demo':True})
    assert response.status_code==200,response.text
    cases=client.get('/api/cases').json()
    assert len(cases)==1 and cases[0]['frames']
    assert client.get('/media/'+cases[0]['frames'][0]['path']).status_code==200
    drafts=client.get('/api/drafts').json()
    assert len(drafts)==1 and '并非 AI' in drafts[0]['content']
    assert client.post('/api/setup/complete',json={'demo':True}).status_code==400
    assert len(client.get('/api/cases').json())==1
    backup=client.post('/api/backups').json()
    assert (core.DATA/'backups'/backup['filename']).is_file()
    assert client.get(backup['url']).status_code==200
    assert client.get('/api/setup/status').json()['completed']
''')


def test_import_preserves_new_machine_config_and_rejects_unsafe_or_nonempty(tmp_path):
    isolated(tmp_path, r'''
import importlib,json,os,sqlite3,zipfile
from pathlib import Path
from backend import core,jobs
from backend.desktop_setup import initialize,import_backup
initialize()
core.save_settings({'dify_keys':{'prototype':{'api_key':'synthetic-test-secret'}}})
case=core.put('case',{'title':'自己的案例'})
jobs.save_transcript(case,'备份里的人工逐字稿')
jobs.case_note(core.get(case['id']))
media=core.media_root()/'sample.txt';media.write_text('test media')
from backend.backup import create_backup
backup=create_backup()
os.environ['VIRALLAB_DATA']=str(Path(os.environ['TEST_ROOT'])/'new-machine')
importlib.reload(core)
initialize()
cfg=core.settings()
import_backup(backup)
assert core.settings()==cfg and not core.settings()['dify_keys']
assert core.records('case')[0]['title']=='自己的案例'
assert (core.media_root()/'sample.txt').read_text()=='test media'
assert '人工逐字稿' in jobs.transcript(core.records('case')[0])
try:import_backup(backup)
except ValueError as e:assert '空资料库' in str(e)
else:raise AssertionError('nonempty import must be refused')
os.environ['VIRALLAB_DATA']=str(Path(os.environ['TEST_ROOT'])/'invalid-import')
importlib.reload(core);initialize()
bad=Path(os.environ['TEST_ROOT'])/'bad.zip'
with zipfile.ZipFile(bad,'w') as archive:
    archive.writestr('../outside.txt','must not be written')
try:import_backup(bad)
except ValueError:pass
else:raise AssertionError('traversal import must be refused')
assert not (core.DATA.parent/'outside.txt').exists()
assert core.records('case')==[]
''')


def test_standalone_writes_from_product_without_dify_or_reference(tmp_path):
    isolated(tmp_path, r'''
import time
from fastapi.testclient import TestClient
from backend.desktop_setup import initialize
from backend import writing_guard,dify
initialize()
def reject_dify(*args,**kwargs):raise AssertionError('Standalone creation must not call Dify')
dify.validate_inputs=reject_dify
writing_guard.generate=lambda *args,**kwargs:'米白色帆布袋，短提手，内侧有一个拉链小袋。'
writing_guard.protect=lambda text,grounding,model,*args,**kwargs:(text,{'status':'passed','grounding_hash':grounding['hash'],'model':model,'version':'test-boundary'})
from backend.app import app
with TestClient(app,base_url='http://127.0.0.1:19231') as client:
    product=client.post('/api/products',json={'name':'帆布袋','content':'米白色、短提手、内侧拉链小袋。'}).json()
    request={'product_id':product['id'],'draft_name':'无需外部服务','request_key':'native-write'}
    preview=client.post('/api/dify/preview',json=request)
    assert preview.status_code==200,preview.text
    assert preview.json()['mode']=='local'
    task=client.post('/api/dify/generate',json={**request,'expected_input_hash':preview.json()['grounding']['hash']}).json()
    assert task['kind']=='local_write'
    for i in range(50):
        task=client.get('/api/tasks/'+task['id']).json()
        if task['status'] in ('succeeded','failed'):break
        time.sleep(.05)
    assert task['status']=='succeeded',task
    draft=client.get('/api/drafts').json()[0]
    assert draft['fact_check']['status']=='passed'
    assert draft['engine']=='local'
    assert '拉链小袋' in draft['content']
''')


def test_standalone_review_does_not_infer_physical_properties_from_material(tmp_path):
    isolated(tmp_path, r'''
from backend.writing_guard import snapshot,mechanical_issues
facts=snapshot('帆布袋','米白色、帆布材质，短提手。防水性能未知。')
assert mechanical_issues('柔软耐用的帆布袋。',facts)
assert mechanical_issues('这款帆布袋防水。',facts)
assert not mechanical_issues('米白色帆布袋，短提手设计看起来很利落。',facts)
provided=snapshot('帆布袋','材质帆布，产品资料说明手感柔软。')
assert not mechanical_issues('柔软的帆布袋。',provided)
''')
