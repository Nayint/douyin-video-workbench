import pytest
from tests.test_api import client

def test_collect_link_without_processing(client):
    response=client.post('/api/cases/link',json={'title':'仅收录','source_url':'https://v.douyin.com/example/','collect_only':True})
    assert response.status_code==200
    assert response.json()['task'] is None
    assert client.get('/api/tasks').json()==[]
    id=response.json()['case']['id']
    task=client.post('/api/cases/'+id+'/research',json={'type':'all','request_key':'analyze-collected'}).json()
    assert task['kind']=='research_all'
    assert client.delete('/api/cases/'+id).status_code==400

def test_remove_preserves_obsidian(client):
    from backend import core
    case=client.post('/api/cases',json={'title':'可移除','transcript':'保留人工资料'}).json()
    path=core.contained(core.settings()['vault_path'],case['note']['path'])
    assert path.exists()
    assert client.delete('/api/cases/'+case['id']).status_code==200
    archived=core.get(case['id'],'archived_case')
    archived_path=core.contained(core.settings()['vault_path'],archived['note']['path'])
    assert archived_path.exists() and '/历史保留/已删除素材/' in archived['note']['path']
    assert '保留人工资料' in archived_path.read_text()
    assert client.get('/api/cases').json()==[]

def test_all_three_research_and_resume_only_failed(client,monkeypatch):
    from backend import core,jobs,ai
    c=client.post('/api/cases',json={'title':'项目名','publication_caption':'发布文案','transcript':'真实内容'}).json()
    image=core.media_root()/'fixture.jpg';image.touch();core.update_record(c['id'],{'cover':'fixture.jpg'})
    task=jobs.enqueue('research_all',c['id'],{},'research-three');calls=[];fail_title=True
    def analyze(kind,material,image):
        calls.append(kind)
        if kind=='title' and fail_title:raise ValueError('模型暂时不可用')
        return 'local-model',{'封面主标题':'双主体展示','画面描述':'本人左侧，产品右侧'} if kind=='cover' else {'result':'通过'}
    monkeypatch.setattr(ai,'analyze',analyze)
    with pytest.raises(ValueError,match='标题研究.*模型暂时不可用'):jobs.work(task)
    assert calls==['video','title','cover_visual']
    assert jobs.task_get(task['id'])['result']['completed']==['video','cover_visual']
    fail_title=False
    jobs.work(jobs.task_get(task['id']))
    assert calls==['video','title','cover_visual','title']

def test_failed_tasks_counted(client):
    from backend import jobs
    t=jobs.enqueue('analysis',None,{'type':'title'},'failure-count')
    jobs.task_update(t['id'],status='failed',error='模型未运行')
    assert client.get('/api/dashboard').json()['pending']==1

def test_archive_can_be_restored(client):
    c=client.post('/api/cases',json={'title':'恢复测试'}).json()
    client.delete('/api/cases/'+c['id'])
    assert client.get('/api/dashboard').json()['total']==0
    assert client.post('/api/cases/'+c['id']+'/restore').status_code==200
    assert client.get('/api/dashboard').json()['total']==1

def test_title_research_only_receives_title(client,monkeypatch):
    from backend import jobs,ai
    c=client.post('/api/cases',json={'title':'案例别名','publication_title':'标题本身','publication_caption':'发布文案','publication_hashtags':['鞋靴'],'transcript':'不属于标题的内容'}).json()
    def analyze(kind,material,image):
        assert 'transcript' not in material and 'title' not in material
        assert material['publication_caption']=='发布文案'
        return 'local-model',{'关键词':'标题'}
    monkeypatch.setattr(ai,'analyze',analyze)
    jobs.work(jobs.enqueue('analysis',c['id'],{'type':'title'},'title-scope'))

def test_upload_can_collect_without_extracting(client,monkeypatch):
    from backend import media
    monkeypatch.setattr(media,'probe',lambda path:{'duration':1,'has_audio':False})
    r=client.post('/api/cases/upload',data={'title':'只保存文件','collect_only':'true'},files={'file':('fixture.mp4',b'fixture','video/mp4')})
    assert r.status_code==200 and r.json()['task'] is None
    assert client.get('/api/tasks').json()==[]

def test_import_and_research_queues_three_part_job(client):
    r=client.post('/api/cases/link',json={'title':'保存并分析','source_url':'https://v.douyin.com/example/','auto_analyze':True}).json()
    assert r['task']['kind']=='research_all'
    again=client.post('/api/cases/'+r['case']['id']+'/research',json={'type':'all','request_key':'another-click'}).json()
    assert again['id']==r['task']['id']

def test_collected_and_researched_are_disjoint(client):
    from backend import core
    a=client.post('/api/cases',json={'title':'仅收录'}).json()
    b=client.post('/api/cases',json={'title':'已研究'}).json()
    core.put('analysis',{'case_id':b['id'],'type':'title','result':{}})
    rows=client.get('/api/cases').json()
    assert next(c for c in rows if c['id']==a['id'])['has_research'] is False
    assert next(c for c in rows if c['id']==b['id'])['has_research'] is True
    d=client.get('/api/dashboard').json()
    assert d['total']==1 and d['analyzed']==1 and d['total_all']==2
    assert [c['id'] for c in d['recent']]==[a['id']]

def test_collected_title_edit_keeps_material_unresearched(client):
    c=client.post('/api/cases/link',json={'title':'原收录标题','source_url':'https://v.douyin.com/example/','collect_only':True}).json()['case']
    r=client.patch('/api/cases/'+c['id'],json={'title':'修改后的收录标题','publication_title':'修改后的发布标题'})
    assert r.status_code==200
    assert r.json()['source_url']==c['source_url']
    assert r.json()['publication_title']=='修改后的发布标题'
    assert client.get('/api/tasks').json()==[]
    row=client.get('/api/cases').json()[0]
    assert row['title']=='修改后的收录标题' and row['has_research'] is False
