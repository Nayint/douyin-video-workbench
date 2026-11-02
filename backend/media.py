"""Media processing is independent of platform acquisition and AI analysis."""
import json
import re
import subprocess
import wave
import numpy as np
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PIL import Image, ImageOps
from .core import settings, media_root
from .public_network import public_addresses, fetch_public

VIDEO_EXT={'.mp4','.mov','.m4v','.webm','.mkv'}
IMAGE_EXT={'.png','.jpg','.jpeg','.webp'}
DOC_EXT={'.txt','.md','.pdf','.docx'}

def command(args, timeout=180):
    try:
        p=subprocess.run(args, capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired: raise ValueError('视频处理超时，请缩短视频或重试')
    if p.returncode: raise ValueError('视频处理失败：'+p.stderr.decode(errors='replace')[-400:])
    return p.stdout

def probe(path):
    d=json.loads(command(['ffprobe','-protocol_whitelist','file,pipe','-v','error','-show_format','-show_streams','-of','json',str(path)],30))
    video=next((s for s in d['streams'] if s['codec_type']=='video'),None)
    if not video: raise ValueError('文件不含有效视频轨道')
    duration=float(d['format'].get('duration',0))
    if not 0<duration<=3600: raise ValueError('V1 支持 1 小时以内、有明确时长的视频')
    return {'duration':duration,'width':video['width'],'height':video['height'],
            'has_audio':any(s['codec_type']=='audio' for s in d['streams'])}

def normalize_image(path):
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1920,1920))
        dest=path.with_suffix('.jpg'); im.save(dest,'JPEG',quality=88)
    return dest

def extract(path, progress):
    info=probe(path); directory=path.parent
    count=min(settings()['frame_count'],max(1,int(info['duration'])))
    frames=[]
    for i in range(count):
        t=min(info['duration']-.05,info['duration']*i/count)
        dest=directory/f'frame-{i:02}.jpg'
        command(['ffmpeg','-nostdin','-y','-v','error','-ss',str(t),'-protocol_whitelist','file,pipe','-i',str(path),'-frames:v','1','-vf','scale=960:-2',str(dest)])
        frames.append({'time':round(t,2),'path':str(dest.relative_to(media_root()))})
    audio=directory/'audio.wav'
    if info['has_audio']:
        command(['ffmpeg','-nostdin','-y','-v','error','-protocol_whitelist','file,pipe','-i',str(path),'-vn','-ar','16000','-ac','1',str(audio)])
    progress('已提取关键帧，准备本地转写',.3)
    return info,frames,audio

_WHISPER=None
_WHISPER_PATH=None

def transcribe(audio, progress):
    global _WHISPER,_WHISPER_PATH
    from faster_whisper import WhisperModel
    model_path=Path(settings()['whisper_model']).expanduser()
    if not model_path.is_dir() or not (model_path/'model.bin').is_file():
        raise ValueError('本地转写模型不完整，请在设置中选择已有 faster-whisper 模型目录；系统不会自动下载')
    if _WHISPER is None or _WHISPER_PATH!=str(model_path):
        progress('加载已有 Whisper 模型（不下载）',.35)
        _WHISPER=WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=6,local_files_only=True)
        _WHISPER_PATH=str(model_path)
    with wave.open(str(audio),'rb') as wav:
        if wav.getframerate()!=16000 or wav.getnchannels()!=1 or wav.getsampwidth()!=2:
            raise ValueError('音频格式异常，需要 FFmpeg 提取的 16kHz 单声道 PCM')
        samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    segments,info=_WHISPER.transcribe(samples,language='zh',word_timestamps=True,beam_size=5,vad_filter=False)
    result=[]
    for seg in segments:
        result.append({'start':round(seg.start,2),'end':round(seg.end,2),'text':seg.text,
            'words':[{'start':w.start,'end':w.end,'word':w.word} for w in (seg.words or [])]})
        progress(f'转写至 {int(seg.end)} 秒',min(.9,.4+.5*seg.end/max(info.duration,1)))
    if not result: raise ValueError('未识别到口播，请检查音轨；可手动录入逐字稿')
    return result

DOUYIN_PAGE_HOSTS={'douyin.com','www.douyin.com','v.douyin.com','iesdouyin.com','www.iesdouyin.com','m.iesdouyin.com'}

def extract_douyin_url(share_text):
    """Accept platform share copy as data, then retain only one verified page URL."""
    candidates=re.findall(r'https?://[^\s<>"\\]+',share_text.strip(),flags=re.I)
    links=[]
    for raw in candidates:
        raw=raw.rstrip("。．，,。!！?？;；:：、）)]}》〉」』'\"")
        try:
            u=urlparse(raw)
            if u.hostname not in DOUYIN_PAGE_HOSTS:continue
            if u.scheme!='https' or u.username or u.password or u.port not in (None,443):
                raise ValueError('抖音链接必须使用 HTTPS，且不能包含账号密码或非标准端口')
        except ValueError:
            raise ValueError('抖音链接格式不安全或端口无效，请复制原始 HTTPS 分享链接')
        normalized=u._replace(fragment='').geturl()
        if normalized not in links:links.append(normalized)
    if not links:raise ValueError('未找到有效抖音链接；可以粘贴抖音完整分享文字，或 https://v.douyin.com/ 开头的链接')
    if len(links)>1:raise ValueError('检测到多个抖音链接，请每次只导入一条视频')
    return links[0]

def public_page_requires_verification(html):
    from html.parser import HTMLParser
    class VisibleText(HTMLParser):
        def __init__(self):super().__init__();self.hidden=0;self.text=[]
        def handle_starttag(self,tag,attrs):
            if tag in ('script','style'):self.hidden+=1
        def handle_endtag(self,tag):
            if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        def handle_data(self,data):
            if not self.hidden:self.text.append(data)
    parser=VisibleText();parser.feed(html)
    visible=''.join(parser.text).strip()
    markers=('verifycenter','captcha-container','请完成验证','安全验证','验证码')
    return any(m in visible.lower() for m in markers) or ('document.cookie' in html and len(visible)<100)

class PublicDouyinAdapter:
    """Public HTML metadata only. No cookies, signature emulation or browser state."""
    name='抖音公开页面'
    @staticmethod
    def validate(raw):
        u=urlparse(raw)
        host=u.hostname or ''
        if u.scheme!='https' or u.username or u.password or u.port not in (None,443):
            raise ValueError('仅接受 HTTPS 抖音公开链接')
        allowed=('douyin.com','iesdouyin.com','douyinvod.com','douyincdn.com','byteimg.com','bytecdn.cn')
        if not any(host==h or host.endswith('.'+h) for h in allowed): raise ValueError('链接域名不在公开适配器允许列表中')
        return u,public_addresses(host)
    def fetch(self,url,limit):
        return fetch_public(url,limit,self.validate)
    def acquire(self,url,directory):
        raw,ctype,final=self.fetch(url,2*1024*1024)
        html=raw.decode('utf-8',errors='replace')
        match=re.search(r'<meta[^>]+(?:property|name)=["\']og:video(?::url)?["\'][^>]+content=["\']([^"\']+)',html,re.I)
        if not match:
            if public_page_requires_verification(html):
                raise ValueError('抖音返回了浏览器安全验证页，需要 JavaScript／Cookie 验证；未尝试绕过。请在此案例上传本地视频，或粘贴逐字稿继续研究')
            raise ValueError('公开视频页面未提供可用媒体地址；请上传本地视频或手动录入，不尝试绕过平台限制')
        import html as h
        video,_,_=self.fetch(h.unescape(match[1]),settings()['max_upload_mb']*1024*1024)
        path=directory/'source.mp4'; path.write_bytes(video); probe(path)
        return path,final
