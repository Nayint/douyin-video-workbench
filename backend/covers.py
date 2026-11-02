"""Download the actual platform cover with bounded, pinned public HTTPS."""
import hashlib
from urllib.parse import urlparse
from . import core,media,source_metadata
from .public_network import fetch_public,public_addresses

def validate(raw):
    u=urlparse(raw);host=u.hostname or ''
    allowed=('douyinpic.com','byteimg.com','douyincdn.com','pstatp.com','toutiaoimg.com','ibytedtos.com','bytecdn.cn')
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not any(host==h or host.endswith('.'+h) for h in allowed):raise ValueError('封面地址不在平台公开图片域名范围内')
    return u,public_addresses(host)

def acquire(id):
    case=core.get(id,'case')
    if not case.get('source_url'):
        if case.get('cover'):return core.contained(core.media_root(),case['cover'])
        raise ValueError('此本地案例还没有封面，请先提取视频关键帧或上传封面')
    data=source_metadata.fetch(case['source_url']);source_metadata.apply(id,data)
    urls=data.get('cover_urls') or []
    if not urls:raise ValueError('原视频没有返回封面地址，可手动上传原封面')
    try:body,ctype,final=fetch_public(urls[0],20*1024*1024,validate)
    except ValueError:raise
    except Exception:raise ValueError('原视频封面下载失败或超时，可稍后重试或上传原封面') from None
    directory=core.media_root()/id;directory.mkdir(parents=True,exist_ok=True)
    path=directory/('source-cover-'+hashlib.sha256(body).hexdigest()[:16]+'.img')
    path.write_bytes(body)
    try:normalized=media.normalize_image(path)
    except Exception:
        path.unlink(missing_ok=True);raise ValueError('平台返回的封面不是有效图片，未进行视觉分析') from None
    path.unlink(missing_ok=True)
    core.update_record(id,{'cover':str(normalized.relative_to(core.media_root())),
        'cover_provenance':{'source':'原视频静态封面','source_url':case['source_url'],'collected_at':core.now(),'sha256':hashlib.sha256(body).hexdigest()}})
    return normalized
