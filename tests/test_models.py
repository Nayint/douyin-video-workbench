import pytest
from tests.test_api import client
from backend import models,core,ai


def test_model_selection_persists_and_drives_inference(client,monkeypatch):
    monkeypatch.setattr(models,'inventory',lambda url=None:[{'name':'new-text','text':True,'vision':False},{'name':'new-vision','text':True,'vision':True}])
    r=client.put('/api/settings',json={'text_model':'new-text','vision_model':'new-vision'})
    assert r.status_code==200
    assert client.get('/api/settings').json()['text_model']=='new-text'
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'message':{'content':'{"正文":"测试"}'}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json):calls.append(json['model']);return Response()
    monkeypatch.setattr(ai.httpx,'Client',Client)
    assert ai.analyze('product',{'test':True})[0]=='new-text'
    assert calls==['new-text']


def test_invalid_models_do_not_change_settings(client,monkeypatch):
    before=core.settings()
    monkeypatch.setattr(models,'inventory',lambda url=None:[{'name':before['text_model'],'text':True,'vision':False}])
    for values in [{'vision_model':before['text_model']},{'text_model':'not-installed'}]:
        r=client.put('/api/settings',json=values)
        assert r.status_code==400
        assert core.settings()==before
