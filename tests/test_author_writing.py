import json
from pathlib import Path
import pytest
from backend import core, jobs, writing_guard, author_profiles
from tests.test_api import client

REAL_PROTECT = writing_guard.protect


def product():
    note=core.sync_note('产品资料','guard-product','米白帆布袋','米白帆布袋，短提手，内侧有拉链小袋，59元。')
    return core.put('product',{'name':'米白帆布袋','note':note,'files':[]})


def register_author(tmp_path,monkeypatch):
    root=tmp_path/'skills';folder=root/'pipi-copywriting';folder.mkdir(parents=True)
    (folder/'SKILL.md').write_text('---\nname: pipi-copywriting\ndescription: 测试作者\n---\n版本：`1.0.1`。\n根据真实事实写作。')
    monkeypatch.setattr(author_profiles,'SKILLS_ROOT',root)
    target=core.DATA/'authors/pipi';target.mkdir(parents=True)
    (target/'writing-card.json').write_text(json.dumps({'author_id':'douyin:xupp141010','display_name':'是皮皮呀','skill_path':str(folder/'SKILL.md')}))
    return folder


def test_numeric_unit_and_first_person_guard():
    g=writing_guard.snapshot('含片','零糖，49.9元一组，两袋补充装。')
    assert writing_guard.mechanical_issues('9.9元三袋，我用了三天。',g)
    assert writing_guard.mechanical_issues('两元。',g)  # 2 is present, but 2 yuan is not.
    assert not writing_guard.mechanical_issues('49.9元一组，两袋补充装。',g)


def test_every_sentence_requires_valid_exact_evidence():
    g=writing_guard.snapshot('袋子','米白帆布袋，59元。')
    with pytest.raises(ValueError,match='覆盖全部'):
        writing_guard.validate_review(['一句','二句'],{'checks':[]},g)
    fabricated={'checks':[{'id':0,'status':'supported','evidence':['能装电脑'],'reason':''}]}
    assert writing_guard.validate_review(['能装电脑。'],fabricated,g)
    duplicate={'checks':[{'id':0,'status':'supported','evidence':['米白'],'reason':''}]*2}
    with pytest.raises(ValueError,match='编号'):
        writing_guard.validate_review(['a','b'],duplicate,g)


def test_clause_segmentation_and_generation_meta():
    g=writing_guard.snapshot('含片','弹射仓设计，方便随身携带，包装标注零糖。')
    text='它是弹射仓设计，这种机械感挺解压的，包装是零糖。'
    assert len(writing_guard.segments(text))==3
    assert not writing_guard.mechanical_issues(text,g)
    assert writing_guard.mechanical_issues('因为没有亲测经历，我就不编造口感了。',g)
    assert not writing_guard.mechanical_issues('最近发现这个设计挺有意思。',g)


def test_user_approved_soft_expressions_are_not_hard_facts():
    g=writing_guard.snapshot('含片','含片，弹射仓设计，包装标注零糖。')
    text='动作很利落，刚好够日常补几颗，吃起来没有负担。我觉得这个设计挺有意思。'
    assert not writing_guard.mechanical_issues(text,g)
    assert writing_guard.mechanical_issues('零卡。',g)
    assert writing_guard.mechanical_issues('我买回来用了一个月。',g)
    rows=writing_guard.segments('这是含片。'+text)
    checks=[{'id':0,'status':'supported','evidence':['含片'],'reason':''}]+[
        {'id':i,'status':'stylistic','evidence':[],'reason':'主观生活分享表达'} for i in range(1,len(rows))]
    assert not writing_guard.validate_review(rows,{'checks':checks},g)


def test_failed_repair_never_returns_publishable_copy(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    monkeypatch.setattr(writing_guard,'check',lambda *a:{'accepted':False,'issues':['容量无证据'],'checks':[]})
    repairs=[]
    monkeypatch.setattr(writing_guard,'generate',lambda *a:(repairs.append(True) or '仍称能装电脑。'))
    with pytest.raises(ValueError,match='未保存正式文案'):
        REAL_PROTECT('能装电脑。',writing_guard.snapshot('袋子','59元'), 'test', 'task',lambda *a:None)
    assert len(repairs)==0
    assert len(list((tmp_path/'writing-audits/task').glob('*.json')))==1


def test_repair_only_deletes_then_requires_fresh_review(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    g=writing_guard.snapshot('帆布袋','米白帆布袋，短提手，内侧有拉链小袋，59元。')
    safe='这个米白帆布袋有短提手，内侧有拉链小袋。价格59元。'
    reviews=[]
    def review(model,copy,grounding):
        reviews.append(copy)
        rows=writing_guard.segments(copy)
        return {'accepted':len(reviews)>1,'issues':['容量无证据'] if len(reviews)==1 else [],'checks':[
            {'id':i,'status':'unsupported' if '电脑' in row else 'supported','evidence':[] if '电脑' in row else ['米白帆布袋'],'reason':''} for i,row in enumerate(rows)]}
    monkeypatch.setattr(writing_guard,'check',review)
    monkeypatch.setattr(writing_guard,'generate',lambda *a:pytest.fail('修订不能调用生成模型补写内容'))
    copy,report=REAL_PROTECT('还能装电脑。'+safe,g,'test','repair',lambda *a:None)
    assert '电脑' not in copy and copy==safe and report['attempts']==2 and len(reviews)==2


def test_author_generation_snapshots_provenance_and_deduplicates(client,tmp_path,monkeypatch):
    register_author(tmp_path,monkeypatch);p=product()
    body={'product_id':p['id'],'author_id':'douyin:xupp141010','writing_mode':'生活分享','draft_name':'作者测试','request_key':'author-test'}
    preview=client.post('/api/dify/preview',json=body)
    assert preview.status_code==200,preview.text
    data=preview.json();assert data['author']['version']=='1.0.1'
    assert '_author' not in data
    body['expected_input_hash']=data['grounding']['hash']
    r=client.post('/api/dify/generate',json=body);assert r.status_code==200,r.text
    assert client.post('/api/dify/generate',json=body).json()['id']==r.json()['id']
    monkeypatch.setattr(writing_guard,'generate',lambda *a:'这个米白帆布袋有短提手，内侧还有拉链小袋。')
    result=jobs.work(r.json());d=core.get(result['draft_id'],'draft')
    assert d['author']['id']=='douyin:xupp141010' and d['case_id'] is None
    assert d['fact_check']['status']=='passed'
    assert d['grounding_hash']==data['grounding']['hash']
    revised=client.post('/api/drafts/'+d['id']+'/versions',json={'content':'人工修改内容。'}).json()
    assert revised['author']['id']==d['author']['id'] and revised['fact_check']['status']=='human_edited'


def test_preview_staleness_unknown_author_and_mode(client,tmp_path,monkeypatch):
    folder=register_author(tmp_path,monkeypatch);p=product()
    body={'product_id':p['id'],'author_id':'douyin:xupp141010','request_key':'stale-author'}
    before=client.post('/api/dify/preview',json=body).json()
    body['expected_input_hash']=before['grounding']['hash']
    (folder/'SKILL.md').write_text((folder/'SKILL.md').read_text()+'新规则')
    assert client.post('/api/dify/generate',json=body).status_code==400
    body.pop('expected_input_hash');body['author_id']='../../settings.json'
    assert client.post('/api/dify/generate',json=body).status_code==400
    body['author_id']='douyin:xupp141010';body['writing_mode']='未知'
    assert client.post('/api/dify/preview',json=body).status_code==400


def test_author_rejection_cannot_create_a_draft(client,tmp_path,monkeypatch):
    register_author(tmp_path,monkeypatch);p=product()
    task=client.post('/api/dify/generate',json={'product_id':p['id'],'author_id':'douyin:xupp141010','request_key':'reject'}).json()
    monkeypatch.setattr(writing_guard,'protect',REAL_PROTECT)
    monkeypatch.setattr(writing_guard,'generate',lambda *a:'9.9元，最后一批。')
    monkeypatch.setattr(writing_guard,'check',lambda *a:{'accepted':False,'issues':['价格无依据'],'checks':[]})
    with pytest.raises(ValueError,match='未保存正式文案'):jobs.work(task)
    assert core.records('draft')==[]
