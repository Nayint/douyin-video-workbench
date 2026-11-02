"""Read video metadata through the user's existing BiliNote downloader, unchanged."""
import json
import subprocess
from pathlib import Path
from datetime import datetime,timezone
from . import core,media

SCRIPT=r'''
import contextlib,io,json,sys
url=json.loads(sys.stdin.read())['url']
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 from app.downloaders.douyin_downloader import DouyinDownloader
 d=DouyinDownloader().fetch_video_info(url)['aweme_detail']
a=d.get('author') or {};v=d.get('video') or {};s=d.get('statistics') or {}
print(json.dumps({'caption':d.get('caption') or d.get('desc') or '',
 'text_extra':[{'hashtag_name':x.get('hashtag_name'),'type':x.get('type')} for x in d.get('text_extra',[])],
 'author':{k:a.get(k) for k in ('nickname','unique_id','short_id','uid')},
 'statistics':{k:s.get(k) for k in ('digg_count','comment_count','collect_count','share_count')},
 'create_time':d.get('create_time'),'video':{k:v.get(k) for k in ('duration','width','height')},
 'cover_urls':(v.get('cover_original_scale') or v.get('origin_cover') or v.get('cover') or {}).get('url_list',[])[:3],
 'video_id':d.get('aweme_id'),'categories':[x.get('tag_name') for x in d.get('video_tag',[]) if x.get('tag_name')]},ensure_ascii=False))
'''

def hashtags(caption,structured=None):
    import re
    # Never treat video_tag categories or other text without # as hashtags.
    tokens=list(dict.fromkeys(re.findall(r'#([^#\s，。！？、,;；:：!?.]+)',caption or '')))
    if structured is not None:
        names={x.get('hashtag_name') for x in structured if x.get('type')==1 and isinstance(x.get('hashtag_name'),str)}
        return [t for t in tokens if t in names]
    return tokens

def fetch(url):
    url=media.extract_douyin_url(url)
    docker=Path('/usr/local/bin/docker')
    if not docker.is_file():raise ValueError('原 BiliNote Docker 环境不可用，暂时无法读取视频详情')
    # The code and container are fixed. URL is JSON input, never executable shell text.
    command=[str(docker),'exec','-i','-w','/app/backend','bilinote','python','-c',SCRIPT]
    try:r=subprocess.run(command,input=json.dumps({'url':url}),text=True,capture_output=True,timeout=60)
    except (subprocess.TimeoutExpired,OSError):raise ValueError('读取原视频详情超时或服务不可用，请稍后重试') from None
    if r.returncode:
        diagnostic=(r.stderr or '').lower()
        if 'cannot connect to the docker daemon' in diagnostic or 'is the docker daemon running' in diagnostic:
            raise ValueError('Docker Desktop 未运行，无法连接原视频获取服务；请先启动 Docker 后重试')
        if 'no such container' in diagnostic or 'is not running' in diagnostic:
            raise ValueError('BiliNote 容器未运行，请启动已有视频获取服务后重试')
        raise ValueError('原 BiliNote 未返回视频详情；可能是链接失效或平台暂时限制，请稍后重试')
    try:return json.loads(r.stdout)
    except json.JSONDecodeError:raise ValueError('视频详情响应格式异常，未猜测或补造数据') from None

def apply(id,data):
    c=core.get(id,'case');caption=data.get('caption','')[:30000];collected=core.now()
    changes={'metadata_collected_at':collected,'metadata_source':'既有 BiliNote 抖音详情','metadata_error':None,
        'source_cover_urls':data.get('cover_urls',[]),'source_video_id':data.get('video_id'),'source_categories':data.get('categories',[])}
    if c.get('publication_source')!='人工补充或校对':
        changes.update(publication_caption=caption.split('#',1)[0].strip(),publication_raw=caption,
            publication_hashtags=hashtags(caption,data.get('text_extra')),
            publication_source='原视频 caption 与 text_extra 双重核验，仅采纳 # 后的原始话题',publication_collected_at=collected,
            publication_hashtag_status='已核验')
    author=data.get('author') or {};video=data.get('video') or {}
    account=author.get('unique_id') or (author.get('short_id') if author.get('short_id') not in ('0',0) else None) or author.get('uid')
    for key,value in [('author',author.get('nickname')),('account',account)]:
        if value and (not c.get(key) or c.get('metadata_source')):changes[key]=str(value)
    for key in ('width','height'):
        if isinstance(video.get(key),(int,float)) and video[key]>0:changes[key]=video[key]
    if isinstance(video.get('duration'),(int,float)) and video['duration']>0:changes['duration']=video['duration']/1000
    if isinstance(data.get('create_time'),(int,float)) and data['create_time']>0:changes['published_at']=datetime.fromtimestamp(data['create_time'],timezone.utc).isoformat()
    old=c.get('metrics') or {}
    if not old.get('source') or old.get('source')=='既有 BiliNote 抖音详情':
        stats=data.get('statistics') or {};metrics={'source':'既有 BiliNote 抖音详情','collected_at':collected}
        for key,remote in [('likes','digg_count'),('comments','comment_count'),('favorites','collect_count'),('shares','share_count')]:
            value=stats.get(remote);metrics[key]=value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None
        changes['metrics']=metrics
    return core.update_record(id,changes)
