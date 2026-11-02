"""Opt-in real integration test. Uses only clearly labelled local QA fixtures."""
import json
import re
import time
import sys
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8765',trust_env=False,timeout=90)
f=json.loads((root/'data/qa/flow.json').read_text());cid=f['case']['id'];pid=json.loads((root/'data/qa/product.json').read_text())['id']
report={}
def wait(id,timeout=2000):
    end=time.monotonic()+timeout;old=None
    while time.monotonic()<end:
        r=c.get('/api/tasks/'+id);r.raise_for_status();t=r.json()
        if t['stage']!=old:print(t['kind'],t['stage'],flush=True);old=t['stage']
        if t['status']=='succeeded':return t
        if t['status'] in ('failed','interrupted'):raise RuntimeError(t['error'] or t['stage'])
        time.sleep(4)
    raise TimeoutError('验收任务等待超时，远端任务未重复提交')
try:
    wait(f['task']['id']);case=c.get('/api/cases/'+cid).json()
    assert case['transcript'].strip() and len(case['frames'])>0 and case['cover'];report['import_transcribe_frames']=True
    for kind in ('video','title','cover'):
        r=c.post('/api/cases/'+cid+'/analyze',json={'type':kind,'request_key':'qa-real-'+kind});r.raise_for_status()
        t=wait(r.json()['id']);report[kind]=t['result'];(root/'data/qa/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    request={'case_id':cid,'product_id':pid,'mode':'prototype','request_key':'qa-real-dify-v1','extra_requirements':'这是软件功能验收，不得将虚构测试产品描述为真实在售产品；正文注明功能验收示例，不编造个人购买或使用经历，控制在200字内。'}
    r=c.post('/api/dify/preview',json=request);r.raise_for_status();report['dify_parameter_preview']=True
    r=c.post('/api/dify/generate',json=request);r.raise_for_status();tid=r.json()['id']
    duplicate=c.post('/api/dify/generate',json=request);assert duplicate.json()['id']==tid;report['deduplicated']=True
    t=wait(tid);did=t['result']['draft_id'];draft=next(d for d in c.get('/api/drafts').json() if d['id']==did)
    body=re.sub(r'^---\n.*?\n---\n\n','',draft['content'],flags=re.S);report['dify']={'task_id':tid,'run_id':t['run_id'],'draft_id':did,'note':draft['note']}
    r=c.post('/api/drafts/'+did+'/versions',json={'content':'人工修订验收：以下仅为功能验收示例。\n\n'+body});r.raise_for_status();report['edited_version']=r.json()['id']
    assert c.get('/api/drafts/'+did+'/export?format=txt').status_code==200
    report['export']=True
    print('REAL_LOCAL_FLOW_PASSED',flush=True)
except Exception as e:
    report['failure']=str(e);print('REAL_LOCAL_FLOW_FAILED',str(e),flush=True);report['failed']=True
finally:(root/'data/qa/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

if report.get("failed"):raise SystemExit(1)
