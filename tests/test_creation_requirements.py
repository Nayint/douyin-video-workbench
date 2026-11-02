import pytest
from backend import core, dify, jobs, spoken
from tests.test_api import client


@pytest.mark.parametrize('requirements', ['', '控制在30秒\n面向带货商家，重点介绍产品库，不要使用最牛和神器。'])
def test_optional_requirements_reach_actual_dify_call(client, monkeypatch, requirements):
    case = core.put('case', {'title': '测试案例', 'transcript': '测试原型文案'})
    note = core.sync_note('产品资料', 'requirements-product', '测试产品', '测试资料')
    product = core.put('product', {'name': '测试产品', 'note': note, 'files': []})
    monkeypatch.setattr(dify, 'validate_inputs', lambda *a: {})
    monkeypatch.setattr(dify, 'upload', lambda *a: {})
    payload = dict(case_id=case['id'], product_id=product['id'], mode='prototype',
                   request_key='requirements-test', extra_requirements=requirements)
    preview = client.post('/api/dify/preview', json=payload)
    assert preview.status_code == 200
    expected = preview.json()['inputs']['extra_requirements']
    assert spoken.FORMAT_REQUIREMENT in expected
    if requirements:
        assert requirements in expected
    seen = []
    def run(mode, inputs, *args):
        seen.append(inputs['extra_requirements'])
        return {'final_copy': '测试生成结果，不代表真实模型输出'}
    monkeypatch.setattr(dify, 'run', run)
    response = client.post('/api/dify/generate', json=payload)
    assert response.status_code == 200
    jobs.work(response.json())
    assert seen == [expected]
    # Changing requirements cannot silently reuse an earlier submission.
    payload['extra_requirements'] = '修改后的新要求'
    assert client.post('/api/dify/generate', json=payload).status_code == 400
