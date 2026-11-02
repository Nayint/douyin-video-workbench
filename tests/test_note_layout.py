from tests.test_api import client

def test_note_moves_into_research_preserving_human_body(client):
    import hashlib
    from backend import core,note_layout
    c=client.post('/api/cases',json={'title':'研究标题','transcript':'逐字稿'}).json()
    old=c['note']['path'];p=core.contained(core.settings()['vault_path'],old)
    assert '/已收录视频/' in old and '研究标题--' in old
    p.write_text(p.read_text()+'\n人工补充内容\n')
    before=p.read_text().split('---\n',2)[2]
    core.put('analysis',{'case_id':c['id'],'type':'video','result':{}})
    note_layout.migrate()
    updated=core.get(c['id']);target=core.contained(core.settings()['vault_path'],updated['note']['path'])
    assert '/研究所/案例/' in updated['note']['path']
    assert target.read_text().split('---\n',2)[2]==before
    assert not p.exists()
    assert '/研究所/案例/' in updated['transcript_note']
    result=core.sync_note('研究所/案例',c['id'],'研究标题','新分析正文')
    assert result['status']=='conflict'
    assert '人工补充内容' in target.read_text()

def test_title_rename_updates_reference(client):
    from backend import core
    c=client.post('/api/cases',json={'title':'旧标题'}).json()
    old=c['note']['path']
    updated=client.patch('/api/cases/'+c['id'],json={'title':'新标题'}).json()
    assert '新标题--' in updated['note']['path']
    assert not core.contained(core.settings()['vault_path'],old).exists()
    assert core.contained(core.settings()['vault_path'],updated['note']['path']).is_file()

def test_product_index_is_not_imported_as_product(client):
    from backend import core,note_layout
    core.save_settings({'product_subdir':'ViralLab/产品资料'})
    note_layout.refresh_indexes()
    assert client.post('/api/products/import').json()['imported']==0
