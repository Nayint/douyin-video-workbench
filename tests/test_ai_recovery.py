import json
import httpx
import pytest
from backend import ai, core
from tests.test_api import client


def valid():
    return {field: {'conclusion': '仅依据素材', 'evidence': '原文片段'} for field in ai.TITLE_FIELDS}


def mock_responses(monkeypatch, responses):
    requests = []
    original = httpx.Client
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=responses.pop(0))
    monkeypatch.setattr(ai.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    return requests


def test_truncated_title_is_retried_and_validated(client, monkeypatch):
    requests = mock_responses(monkeypatch, [
        {'message': {'content': '{"broken":'}, 'done_reason': 'length', 'eval_count': 3200},
        {'message': {'content': json.dumps(valid())}, 'done_reason': 'stop'}])
    assert ai.analyze('title', {'publication_caption': '原始内容'})[1] == valid()
    assert len(requests) == 2
    assert requests[0]['format']['required'] == list(ai.TITLE_FIELDS)
    assert requests[1]['options']['num_predict'] > requests[0]['options']['num_predict']
    diagnostics = list((core.DATA / 'model-diagnostics').glob('*.json'))
    assert len(diagnostics) == 1
    assert '原始内容' not in diagnostics[0].read_text()


def test_invalid_fields_never_saved_as_success(client, monkeypatch):
    requests = mock_responses(monkeypatch, [{'message': {'content': '{}'}}] * 2)
    with pytest.raises(ValueError, match='自动重试后仍失败'):
        ai.analyze('title', {})
    assert len(requests) == 2


def test_title_prompt_keeps_verified_tags_readable_and_flat(client, monkeypatch):
    requests = mock_responses(monkeypatch, [
        {'message': {'content': json.dumps(valid())}, 'done_reason': 'stop'}])
    ai.analyze('title', {'publication_caption': '原始发布文案',
                         'hashtags': ['短视频带货', '电商干货'],
                         'publication_raw': '原始发布文案 #未核实分类'})
    prompt = requests[0]['messages'][1]['content']
    assert '每个字段仅含conclusion和evidence两个字符串' in prompt
    assert '#短视频带货、#电商干货' in prompt
    assert '未核实分类' not in prompt
    assert '不嵌套子项目' in prompt


def test_fenced_complete_json():
    assert ai.parse_result('```json\n' + json.dumps(valid()) + '\n```', 'title') == valid()
    with pytest.raises(ValueError):
        ai.parse_result('{"unfinished":', 'title')
