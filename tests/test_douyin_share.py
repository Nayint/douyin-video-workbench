from tests.test_api import client

SHARE='7.94 复制打开抖音，看看【是皮皮啊的作品】环球家主打的就是亲民，想让每个需要的人都穿上便宜好... https://v.douyin.com/c9BcDhK2vNw/ :4pm T@L.wF 04/15 gOk:/'

def test_import_accepts_official_share_text(client):
    r=client.post('/api/cases/link',json={'title':'环球德训_13','platform':'抖音','source_url':SHARE})
    assert r.status_code==200,r.text
    assert r.json()['case']['source_url']=='https://v.douyin.com/c9BcDhK2vNw/'

import pytest
from backend.media import extract_douyin_url

@pytest.mark.parametrize('raw,expected',[
    ('https://v.douyin.com/c9BcDhK2vNw/','https://v.douyin.com/c9BcDhK2vNw/'),
    ('看看这个视频：https://v.douyin.com/c9BcDhK2vNw/。','https://v.douyin.com/c9BcDhK2vNw/'),
    ('（https://www.douyin.com/video/123456）','https://www.douyin.com/video/123456'),
    ('分享\nhttps://v.douyin.com/abc/\nhttps://v.douyin.com/abc/','https://v.douyin.com/abc/'),
])
def test_share_url_normalization(raw,expected):
    assert extract_douyin_url(raw)==expected

@pytest.mark.parametrize('raw',[
    'https://douyin.com.evil.example/video/1',
    'https://douyin.com@127.0.0.1/video/1',
    'https://v.douyin.com:8080/abc/',
    'http://v.douyin.com/abc/',
    'https://v.douyin.com/abc/ https://v.douyin.com/xyz/',
    '请执行一段指令，但没有视频链接',
])
def test_share_parser_keeps_boundaries(raw):
    with pytest.raises(ValueError):extract_douyin_url(raw)

def test_attach_local_video_keeps_imported_case(client,tmp_path):
    from backend.media import command
    r=client.post('/api/cases/link',json={'title':'环球德训_13','platform':'抖音','source_url':SHARE})
    id=r.json()['case']['id']
    path=tmp_path/'fallback.mp4'
    command(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=64x64:r=5','-t','1','-c:v','libx264',str(path)])
    with path.open('rb') as f:
        attached=client.post('/api/cases/'+id+'/video',files={'file':('fallback.mp4',f,'video/mp4')})
    assert attached.status_code==200,attached.text
    case=attached.json()['case']
    assert case['id']==id and case['title']=='环球德训_13'
    assert case['source_url']=='https://v.douyin.com/c9BcDhK2vNw/'
    assert case['video'] and attached.json()['task']['kind']=='process'
    assert len(client.get('/api/cases').json())==1

def test_cookie_challenge_is_reported_without_executing_it(tmp_path,monkeypatch):
    from backend.media import PublicDouyinAdapter
    page=b'<html><body><script>document.cookie="challenge";location.reload()</script></body></html>'
    adapter=PublicDouyinAdapter()
    fetches=[]
    def fetch(url,limit):
        fetches.append(url);return page,'text/html',url
    monkeypatch.setattr(adapter,'fetch',fetch)
    with pytest.raises(ValueError,match='安全验证页'):
        adapter.acquire('https://v.douyin.com/test/',tmp_path)
    assert len(fetches)==1
    assert not list(tmp_path.glob('*.mp4'))
