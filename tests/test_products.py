import io
import zipfile
from tests.test_api import client
from backend import core,jobs,ai,products


def test_product_analyze_and_update_versions(client,monkeypatch):
    p=client.post('/api/products',json={'name':'测试产品','content':'棉质，蓝色'}).json()
    seen=[]
    def analyze(kind,material,image=None):
        seen.append(material)
        return 'local-test',{'正文':'棉质，蓝色。'+material['用户更新要求']}
    monkeypatch.setattr(ai,'analyze',analyze)
    for i,instruction in enumerate(['','新增黑色']):
        t=client.post('/api/products/'+p['id']+'/analyze',json={'request_key':'product-'+str(i),'instruction':instruction}).json()
        result=jobs.work(t)
        assert result['version_id']
    assert len(client.get('/api/products/'+p['id']+'/versions').json())==2
    assert '新增黑色' in client.get('/api/products').json()[0]['content']
    assert core.get(p['id'])['analysis_status']=='ready'


def test_product_conflict_keeps_manual_body(client,monkeypatch):
    p=client.post('/api/products',json={'name':'产品','content':'原文'}).json()
    path=core.contained(core.settings()['vault_path'],p['note']['path']);path.write_text(path.read_text()+'人工修改')
    monkeypatch.setattr(ai,'analyze',lambda *args:('local',{'正文':'AI结果'}))
    import pytest
    with pytest.raises(ValueError,match='人工修改'):jobs.work(jobs.enqueue('product_analysis',p['id'],{'instruction':''},'conflict-product'))
    assert '人工修改' in path.read_text()
    assert len(core.records('product_version'))==1


def test_docx_extraction(tmp_path):
    p=tmp_path/'sample.docx'
    with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>真实规格</w:t></w:r></w:p></w:body></w:document>')
    assert '真实规格' in products.extract(p)[0]


def test_product_image_uses_vision(client,monkeypatch):
    from PIL import Image
    p=client.post('/api/products',json={'name':'图片产品','content':'附件待分析'}).json()
    raw=io.BytesIO();Image.new('RGB',(80,80),'white').save(raw,format='PNG')
    response=client.post('/api/products/'+p['id']+'/files',files={'file':('product.png',raw.getvalue(),'image/png')})
    assert response.status_code==200
    calls=[]
    def analyze(kind,material,image=None):
        calls.append(kind)
        if kind=='product_image':
            assert image.exists()
            return 'vision',{'外观':'白色图片，未知规格'}
        assert '白色图片' in str(material)
        return 'text',{'正文':'产品规格未知'}
    monkeypatch.setattr(ai,'analyze',analyze)
    jobs.work(jobs.enqueue('product_analysis',p['id'],{'instruction':''},'product-image'))
    assert calls==['product_image','product']


def test_scanned_pdf_renders_for_local_vision(tmp_path):
    from pypdf import PdfWriter
    p=tmp_path/'scan.pdf';writer=PdfWriter();writer.add_blank_page(width=200,height=200)
    with p.open('wb') as f:writer.write(f)
    text,images=products.extract(p)
    assert text=='' and len(images)==1 and images[0].exists()
