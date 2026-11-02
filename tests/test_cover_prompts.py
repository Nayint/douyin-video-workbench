from tests.test_api import client

def test_obsidian_link_uses_encoded_absolute_path(client):
    from backend import core
    from urllib.parse import urlparse,parse_qs
    c=client.post('/api/cases',json={'title':'中文 & 空格'}).json()
    uri=c['note']['uri'];q=parse_qs(urlparse(uri).query)
    assert 'vault' not in q
    assert q['path']==[str(core.contained(core.settings()['vault_path'],c['note']['path']))]
    assert '%2F' in uri and '%20' in uri
    old=core.get(c['id']);old['note']['uri']='obsidian://open?vault=wrong'
    core.put('case',old,c['id']);core.repair_note_uris()
    assert core.get(c['id'])['note']['uri']==uri

def test_cover_prompt_uses_product_and_fixed_profile_without_image(client,monkeypatch):
    from backend import core,jobs,ai
    c=client.post('/api/cases',json={'title':'案例','transcript':'原视频文案'}).json()
    p=client.post('/api/products',json={'name':'产品','content':'真实产品资料'}).json()
    core.update_record(c['id'],{'cover_product_id':p['id'],'cover_reference_style':'大字、单一主体'})
    def analyze(kind,material,image):
        assert image is None and material['product_id']==p['id']
        assert '真实产品资料' in material['product_material']
        assert material['transcript']=='原视频文案\n'
        assert '没有参考图片' in material['reference_notice']
        return 'local-model',{'封面主标题':'整理桌面','画面描述':'右下摆放产品','产品呈现':'依照产品实拍图'}
    monkeypatch.setattr(ai,'analyze',analyze)
    r=jobs.work(jobs.enqueue('analysis',c['id'],{'type':'cover'},'cover-prompt'))
    a=core.get(r['analysis_id'])
    assert core.settings()['cover_style_profile'] in a['result']['可复制的封面提示词']
    assert '/封面提示词/' in a['note']['path']

def test_cover_draft_must_match_product(client):
    import pytest
    from backend import core,jobs,cover_prompts
    c=client.post('/api/cases',json={'title':'案例','transcript':'原文'}).json()
    p=client.post('/api/products',json={'name':'产品A','content':'资料A'}).json()
    p2=client.post('/api/products',json={'name':'产品B','content':'资料B'}).json()
    d=jobs.draft_version(c['id'],p['id'],'原创文案')
    case={**c,'cover_product_id':p2['id'],'cover_draft_id':d['id']}
    with pytest.raises(ValueError,match='不一致'):cover_prompts.material(case,'原文')
    case['cover_product_id']=p['id']
    material,image=cover_prompts.material(case,'原文')
    assert '原创文案' in material['transcript'] and material['draft_id']==d['id']
