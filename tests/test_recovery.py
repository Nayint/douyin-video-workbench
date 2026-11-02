import json
from backend import dify, jobs
from tests.test_api import client

def test_dify_recovery_does_not_submit_again(client,monkeypatch):
    from backend import core
    case=core.put('case',{'title':'恢复案例'})
    note=core.sync_note('产品资料','recovery-product','恢复产品','恢复测试产品的事实资料。')
    product=core.put('product',{'name':'恢复产品','note':note})
    task=jobs.enqueue('dify',case['id'],{'mode':'prototype','product_id':product['id'],'inputs':{}},'recover-fixed')
    jobs.task_update(task['id'],status='interrupted',run_id='remote-existing')
    calls=[]
    def request(mode,method,path,**kwargs):
        calls.append((method,path));return {'status':'succeeded','outputs':{'final_copy':'真实远端已完成结果'}}
    monkeypatch.setattr(dify,'request',request)
    for _ in range(2):
        r=client.post('/api/tasks/'+task['id']+'/resume');assert r.status_code==200
    assert len(core.records('draft'))==1
    assert all(method=='GET' for method,path in calls)

def test_analysis_revision_preserves_original(client):
    from backend import core
    old=core.put('analysis',{'case_id':None,'type':'title','model':'local','prompt_version':'v1','result':{'观察':'旧结论'},'human':False})
    r=client.post('/api/analyses/'+old['id']+'/versions',json={'result':{'观察':'人工修订'}})
    assert r.status_code==200
    assert r.json()['parent_id']==old['id']
    assert core.get(old['id'])['result']['观察']=='旧结论'
