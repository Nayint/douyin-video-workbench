"""Specialize a Dify graph for ViralLab's already-extracted product brief.

Used only for immutable workbench runtime versions. Standalone source apps keep
attachment recognition. IDs/output types stay stable for existing selectors.
"""
PRODUCT_REUSE_VERSION = 'product-brief-reuse-v1'

def reuse_product_brief(graph):
    start=next(n for n in graph['nodes'] if n['data']['type']=='start')
    start_id=start['id']
    variables={v['variable'] for v in start['data'].get('variables',[])}
    if not {'source_material','product_files'} <= variables:
        raise ValueError('Product brief input contract changed')
    expected={'1791968000003':('document-extractor','读取产品 PDF / Word / 文本'),
              '1791968000005':('llm','本地识别产品图片'),
              '1791968000006':('llm','建立新产品事实底稿')}
    found={n['id']:n for n in graph['nodes'] if n['id'] in expected}
    if set(found)!=set(expected):raise ValueError('Product extraction graph changed')
    for id,(kind,title) in expected.items():
        node=found[id]
        if (node['data']['type'],node['data']['title'])!=(kind,title):
            raise ValueError('Product extraction node changed')
        fact=id=='1791968000006'
        code=('def main(source_material: str) -> dict:\n'
              '    if not source_material.strip():\n'
              '        raise ValueError("请先在产品库完成产品资料提取或填写正文")\n'
              '    return {"text": source_material}\n') if fact else (
              'def main() -> dict:\n    return {"text": '+('[]' if kind=='document-extractor' else '""')+'}\n')
        node['data']={'type':'code','title':'复用产品库事实正文' if fact else '跳过产品附件重复识别',
            'desc':'工作台已完成提取；以本次冻结的产品库正文为准。',
            'code_language':'python3','code':code,
            'variables':[{'variable':'source_material','value_selector':[start_id,'source_material']}] if fact else [],
            'outputs':{'text':{'type':'array[string]' if kind=='document-extractor' else 'string','children':None}},
            'selected':False}
    for edge in graph['edges']:
        for side in ('source','target'):
            if edge[side] in expected:
                edge.setdefault('data',{})[side+'Type']='code'
    return {'version':PRODUCT_REUSE_VERSION,'replaced_nodes':list(expected),
            'attachment_upload':False,'product_fact_source':'source_material'}
