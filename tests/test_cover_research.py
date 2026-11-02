import io
import pytest
from PIL import Image
from tests.test_api import client

def test_actual_cover_download_validates_and_saves(client,monkeypatch):
    from backend import covers,core
    c=client.post('/api/cases',json={'title':'封面','source_url':'https://v.douyin.com/example/'}).json()
    out=io.BytesIO();Image.new('RGB',(100,150),'green').save(out,format='PNG')
    monkeypatch.setattr(covers.source_metadata,'fetch',lambda url:{'caption':'原文','cover_urls':['https://p3.douyinpic.com/cover.jpg']})
    monkeypatch.setattr(covers,'fetch_public',lambda *args:(out.getvalue(),'image/png',args[0]))
    path=covers.acquire(c['id'])
    assert path.exists() and path.suffix=='.jpg'
    assert core.get(c['id'])['cover_provenance']['source']=='原视频静态封面'

def test_visual_analysis_receives_real_image(client,monkeypatch):
    from backend import core,jobs,ai
    c=client.post('/api/cases',json={'title':'不研究名称'}).json()
    image=core.media_root()/'cover.jpg';image.write_bytes(b'fixture')
    core.update_record(c['id'],{'cover':'cover.jpg'})
    def analyze(kind,material,source):
        assert kind=='cover_visual' and source==image and 'title' not in material
        return 'vision-model',{'构图':'仅依据图片'}
    monkeypatch.setattr(ai,'analyze',analyze)
    r=jobs.work(jobs.enqueue('analysis',c['id'],{'type':'cover_visual'},'visual'))
    assert '/封面研究/' in core.get(r['analysis_id'])['note']['path']

def test_cover_rejects_private_or_untrusted_domain():
    from backend import covers
    for url in ['http://p3.douyinpic.com/a','https://127.0.0.1/a','https://evil.example/a']:
        with pytest.raises(ValueError):covers.validate(url)
