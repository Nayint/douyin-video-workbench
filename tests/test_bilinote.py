from tests.test_api import client

def test_link_uses_existing_dify_ingestion(client,monkeypatch):
    from backend import core,jobs,bilinote
    case=core.put('case',{'title':'测试','source_url':'https://v.douyin.com/example/'})
    task=jobs.enqueue('link',case['id'],{},'existing-service')
    def acquire(url,title,remote_id,progress,submit=False):
        assert jobs.task_get(task['id'])['remote_task_id']==remote_id
        return {'transcript':{'full_text':'真实逐字稿','segments':[{'start':0,'end':2,'text':'真实逐字稿'}]}}
    monkeypatch.setattr(bilinote,'acquire',acquire)
    monkeypatch.setattr(jobs.source_metadata,'fetch',lambda url:{'caption':'测试发布文案','text_extra':[]})
    jobs.work(task)
    assert '真实逐字稿' in jobs.transcript(core.get(case['id']))
    assert core.get(case['id'])['ingestion']['service']=='BiliNote'

def test_payload_matches_existing_dify_and_resume_does_not_submit(client,monkeypatch):
    import httpx
    from backend import bilinote,core
    core.save_settings({'text_model':'selected-installed-model'})
    requests=[]
    submitted=False
    def handle(request):
        nonlocal submitted
        requests.append(request)
        if request.method=='POST':
            submitted=True
            import json
            body=json.loads(request.content)
            assert body['platform']=='douyin' and body['provider_id']=='ollama'
            assert body['model_name']=='selected-installed-model' and body['screenshot'] is False
            assert body['task_id']=='stable-id'
            return httpx.Response(200,json={'code':0,'data':{'task_id':'stable-id'}})
        result={'status':'SUCCESS','result':{'transcript':{'full_text':'原文','segments':[]}}} if submitted else {'status':'PENDING'}
        return httpx.Response(200,json={'code':0,'data':result})
    original=httpx.Client
    monkeypatch.setattr(bilinote.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    bilinote.acquire('https://v.douyin.com/example/','标题','stable-id',lambda *a:None,submit=True)
    requests.clear()
    bilinote.acquire('https://v.douyin.com/example/','标题','stable-id',lambda *a:None)
    assert all(r.method=='GET' for r in requests)

def test_publication_metadata_preserves_original_text():
    from backend.bilinote import publication_metadata
    r=publication_metadata({'audio_meta':{'title':'原视频标题','raw_info':{'tags':'原发布文案 #话题一 #话题二'}}})
    assert r['publication_title']=='原视频标题'
    assert r['publication_caption']=='原发布文案'
    assert r['publication_hashtags']==[]  # merged legacy field is not trustworthy
    assert r['publication_raw']=='原发布文案 #话题一 #话题二'

def test_initial_connection_failure_can_be_safely_resubmitted(client,monkeypatch):
    import httpx,pytest
    from backend import bilinote,core,jobs
    case=core.put('case',{'title':'连接失败恢复','source_url':'https://v.douyin.com/example/'})
    task=jobs.enqueue('link',case['id'],{},'connection-recovery')
    def handle(request):
        raise httpx.ConnectError('offline',request=request)
    original=httpx.Client
    monkeypatch.setattr(bilinote.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    with pytest.raises(bilinote.AcquisitionConnectionError,match='Docker'):
        jobs.work(task)
    assert jobs.task_get(task['id'])['remote_task_id'] is None


def test_uncertain_post_failure_preserves_remote_id(client,monkeypatch):
    import httpx,pytest
    from backend import bilinote,core,jobs
    case=core.put('case',{'title':'提交结果不确定','source_url':'https://v.douyin.com/example/'})
    task=jobs.enqueue('link',case['id'],{},'uncertain-post')
    def handle(request):
        if request.method=='GET':return httpx.Response(200,json={'code':0,'data':{'status':'PENDING'}})
        raise httpx.ReadTimeout('response lost',request=request)
    original=httpx.Client
    monkeypatch.setattr(bilinote.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    with pytest.raises(bilinote.AcquisitionConnectionError):jobs.work(task)
    assert jobs.task_get(task['id'])['remote_task_id']

def test_metadata_docker_unavailable_is_not_platform_error(client,monkeypatch):
    import subprocess,pytest
    from backend import source_metadata
    monkeypatch.setattr(source_metadata.subprocess,'run',lambda *a,**kw:subprocess.CompletedProcess(a[0],1,'','Cannot connect to the Docker daemon. Is the docker daemon running?'))
    with pytest.raises(ValueError,match='Docker Desktop 未运行'):
        source_metadata.fetch('https://v.douyin.com/example/')
