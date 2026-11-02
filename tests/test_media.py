import wave
import subprocess
import numpy as np
from backend.media import command,probe,PublicDouyinAdapter
import pytest

def test_public_adapter_refuses_private_and_unknown_domains():
    for url in ('http://127.0.0.1/x','https://evil.example/video','https://douyin.com@127.0.0.1/x'):
        with pytest.raises(ValueError):PublicDouyinAdapter.validate(url)

def test_real_local_video_probe(tmp_path):
    path=tmp_path/'tiny.mp4'
    command(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=64x64:r=5','-t','1','-c:v','libx264',str(path)])
    p=probe(path)
    assert p['width']==64 and p['has_audio'] is False
    assert .9<=p['duration']<=1.2

def test_whisper_accepts_pcm_without_pyav(tmp_path,monkeypatch):
    import backend.media as media
    from types import SimpleNamespace
    path=tmp_path/'pcm.wav'
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(np.zeros(1600,dtype=np.int16).tobytes())
    class Decoder:
        def transcribe(self,samples,**kwargs):
            assert isinstance(samples,np.ndarray) and len(samples)==1600
            return iter([SimpleNamespace(start=0,end=.1,text='测试',words=[])]),SimpleNamespace(duration=.1)
    model=tmp_path/'mock-model';model.mkdir();(model/'model.bin').touch()
    monkeypatch.setattr(media,'settings',lambda:{'whisper_model':str(model)})
    monkeypatch.setattr(media,'_WHISPER',Decoder())
    monkeypatch.setattr(media,'_WHISPER_PATH',media.settings()['whisper_model'])
    assert media.transcribe(path,lambda *args:None)[0]['text']=='测试'
