"""First-install flow with generated media, no private data or external AI services."""
import os
from pathlib import Path
import subprocess
import sys


def test_first_install(tmp_path):
    env = {**os.environ, 'VIRALLAB_DATA': str(tmp_path / 'data'),
           'ACCEPTANCE_ROOT': str(tmp_path)}
    result = subprocess.run([sys.executable, '-c', r'''
import os, subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from backend import core, jobs, media
from backend.app import app
root=Path(os.environ['ACCEPTANCE_ROOT'])
core.save_settings({'vault_path': str(root/'vault'), 'whisper_model':str(root/'missing-model')})
video=root/'sample.mp4'
subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=blue:s=160x120:d=1','-c:v','mpeg4',str(video)],check=True)
with TestClient(app, base_url='http://127.0.0.1:8765') as client:
    assert client.get('/api/health').status_code==200
    assert client.get('/api/cases').json()==[]
    assert client.get('/api/authors').json()==[]
    assert client.get('/api/creation/references').json()==[]
    case=client.post('/api/cases',json={'title':'示例','transcript':'这是人工录入的示例逐字稿。'})
    assert case.status_code==200,case.text
    assert '示例逐字稿' in client.get('/api/cases/'+case.json()['id']).json()['transcript']
    product=client.post('/api/products',json={'name':'示例产品','content':'材质为棉，容量未知。'})
    assert product.status_code==200,product.text
    with video.open('rb') as f:
        uploaded=client.post('/api/cases/upload',data={'collect_only':'true'},files={'file':('sample.mp4',f,'video/mp4')})
    assert uploaded.status_code==200,uploaded.text
    record=uploaded.json()['case']
    info,frames,audio=media.extract(core.media_root()/record['video'],lambda *args:None)
    assert frames and not info['has_audio']
    assert client.get('/media/'+frames[0]['path']).status_code==200
    draft=jobs.draft_version(case.json()['id'],product.json()['id'],'示例文案，仅用于验收。')
    assert '示例文案' in client.get('/api/drafts/'+draft['id']+'/export?format=txt').text
    try:
        media.transcribe(root/'missing.wav',lambda *args:None)
    except ValueError as error:
        assert '模型' in str(error)
    else:
        raise AssertionError('Missing transcription model must be reported')
    preview=client.post('/api/dify/preview',json={'product_id':product.json()['id'],'request_key':'first-install'})
    assert preview.status_code==400,preview.text
print('first-install flow passed')
'''], env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
