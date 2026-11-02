"""Reuse the existing local Dify ingestion service, without reading its credentials."""
import time
import httpx
from . import core

class AcquisitionConnectionError(ValueError):
    def __init__(self, message, submission_not_attempted=False):
        super().__init__(message)
        self.submission_not_attempted = submission_not_attempted

STAGES={'PENDING':'排队中','PARSING':'解析链接','DOWNLOADING':'下载音频','TRANSCRIBING':'转写音频','SUMMARIZING':'整理内容','FORMATTING':'整理格式','SAVING':'保存结果'}

def acquire(url,title,remote_id,progress,submit=False):
    cfg=core.settings()
    base=core.local_url(cfg['bilinote_url'])
    def checked(response):
        response.raise_for_status()
        body=response.json()
        if body.get('code')!=0:
            raise ValueError('BiliNote 获取失败：'+str(body.get('msg','未知服务错误'))[:300])
        return body.get('data') or {}
    submission_started=False
    try:
        with httpx.Client(timeout=30,trust_env=False) as client:
            # The caller persists the ID before submitting. Existing tasks resume by polling.
            status=checked(client.get(base+'/api/task_status/'+remote_id))
            if submit and status.get('status')=='PENDING':
                submission_started=True
                checked(client.post(base+'/api/generate_note',json={
                    'task_id':remote_id,'video_url':url,'video_name':title[:120],
                    'platform':'douyin','quality':'fast','provider_id':'ollama','model_name':cfg['text_model'],
                    'style':'简洁','format':[],'screenshot':False,'link':False,
                    'video_understanding':False,'extras':'简洁记录视频内容。'}))
            deadline=time.monotonic()+1800
            while True:
                status=checked(client.get(base+'/api/task_status/'+remote_id))
                stage=status.get('status')
                if stage=='SUCCESS':
                    result=status.get('result') or {}
                    transcript=result.get('transcript') or {}
                    if not transcript.get('full_text') and not transcript.get('segments'):
                        raise ValueError('BiliNote 已结束，但没有返回逐字稿')
                    return result
                if stage=='FAILED':raise ValueError('BiliNote 视频处理失败，请查看原服务任务记录')
                if time.monotonic()>deadline:raise ValueError('BiliNote 处理超时；远端任务编号已保留，可继续查询')
                progress('BiliNote · '+STAGES.get(stage,str(stage)),.3 if stage=='TRANSCRIBING' else .15)
                time.sleep(2)
    except (httpx.HTTPError,ValueError) as e:
        if isinstance(e,ValueError):raise
        message = ('视频获取服务无法连接：请先启动 Docker Desktop，并确认 BiliNote 服务已运行'
                   if isinstance(e,httpx.ConnectError) else '视频获取服务响应超时或异常，请确认 BiliNote 运行状态')
        raise AcquisitionConnectionError(message, submission_not_attempted=submit and not submission_started) from None

def publication_metadata(result):
    """Keep original service text; do not mistake the workbench name for a post title."""
    import re
    meta=result.get('audio_meta') or {}
    raw=meta.get('raw_info') or {}
    combined=raw.get('desc') or raw.get('caption') or raw.get('tags') or ''
    if not isinstance(combined,str):combined=''
    return {'publication_title':str(meta.get('title') or ''),
        'publication_caption':combined.split('#',1)[0].strip(),
        'publication_hashtags':[],'publication_hashtag_status':'源服务返回了合并文本，待从原视频核验#话题；未把分类拼接成标签',
        'publication_raw':combined,'publication_source':'BiliNote 原视频元信息（文案与标签原文保留；服务可能合并分类）',
        'publication_collected_at':core.now()}
