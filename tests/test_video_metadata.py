from tests.test_api import client

def test_only_actual_hashtags_are_accepted():
    from backend.source_metadata import hashtags
    text='难怪动画片里的人都戴睡帽！#睡帽'
    assert hashtags(text,[{'hashtag_name':'睡帽','type':1},{'hashtag_name':'服饰','type':1}])==['睡帽']
    assert hashtags('好物 #甲 #乙，日常穿搭')==['甲','乙']
    assert hashtags('无标签，睡帽服饰穿搭')==[]

def test_real_metadata_populates_overview_without_categories_becoming_tags(client):
    from backend import core,source_metadata
    c=client.post('/api/cases',json={'title':'不要分析这个名字'}).json()
    r=source_metadata.apply(c['id'],{'caption':'发布内容#睡帽','text_extra':[{'hashtag_name':'睡帽','type':1}],
        'categories':['服饰','穿搭'],'author':{'nickname':'原作者','unique_id':'account'},
        'video':{'duration':79734,'width':1080,'height':1920},'create_time':1789214601,
        'statistics':{'digg_count':2641,'comment_count':98,'collect_count':1004,'share_count':1101},'video_id':'123'})
    assert r['author']=='原作者' and r['account']=='account'
    assert r['duration']==79.734 and r['metrics']['likes']==2641
    assert r['publication_hashtags']==['睡帽']
    assert r['title']=='不要分析这个名字'

def test_cover_can_generate_without_product_profile(client,monkeypatch):
    from backend import core,jobs,ai,cover_prompts
    c=client.post('/api/cases',json={'title':'项目名','transcript':'睡帽相关口播内容'}).json()
    def analyze(kind,m,image):
        assert m['product_id'] is None and '占位' in m['product_material']
        return 'local-model',{'封面主标题':'适合你的睡帽','画面描述':'本人在左，待替换产品在右'}
    monkeypatch.setattr(ai,'analyze',analyze)
    r=jobs.work(jobs.enqueue('analysis',c['id'],{'type':'cover'},'no-product'))
    a=core.get(r['analysis_id']);prompt=a['result']['可复制的封面提示词']
    assert cover_prompts.PERSON_PRODUCT_RULES in prompt
    assert '本人参考照片' in prompt and '产品' in prompt
    assert '未选择真实产品资料' in a['result']['产品资料状态']

def test_cover_rules_are_not_duplicated():
    from backend import cover_prompts
    result=cover_prompts.assemble({'封面主标题':'不采用猜测标题','画面描述':'不采用猜测外貌'},
        {'product_id':None,'topic_tags':['睡帽'],'style_profile':cover_prompts.DEFAULT_STYLE,'reference_notice':'未提供图片','product_notice':'占位'})
    prompt=result['可复制的封面提示词']
    assert prompt.count(cover_prompts.PERSON_PRODUCT_RULES)==1
    assert result['封面主标题']=='睡帽观察笔记'
    assert '真实产品照片' in result['产品呈现']
