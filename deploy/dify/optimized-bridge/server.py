"""Local BiliNote adapter. Dify controls the polling loop and all copywriting."""
import json
import hashlib
import os
import re
import sqlite3
import threading
import time
import uuid
import sys
sys.path.insert(0, "/bridge/vendor")
from opencc import OpenCC
SIMPLIFIED = OpenCC("t2s")
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen

UPSTREAM = os.getenv('BILINOTE_URL', 'http://host.docker.internal:18080').rstrip('/')
STATE = Path('/data/optimized.sqlite3')
STATE.parent.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
COPY_DIR = Path('/obsidian-copy')
HOST_COPY_DIR = os.getenv('HOST_COPY_DIR', '/obsidian-copy')
with sqlite3.connect(STATE) as db:
    db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, url TEXT NOT NULL, task TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (fingerprint TEXT PRIMARY KEY, id TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS videos (key TEXT PRIMARY KEY, task TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS exports (id TEXT PRIMARY KEY, filename TEXT NOT NULL, content TEXT NOT NULL)')


def upstream(path, payload=None):
    request = Request(UPSTREAM + '/api/' + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
    if result.get('code') != 0:
        raise ValueError(result.get('msg') or 'BiliNote 返回错误')
    return result.get('data') or {}


def start(payload):
    request_id = str(uuid.UUID(payload['request_id']))
    video_name = str(payload.get('video_name') or '').strip()
    if not video_name or len(video_name) > 120:
        raise ValueError('请填写视频名称（最多120字）。')
    match = re.search(r'https?://[^\s<>]+', payload.get('video_url', ''))
    if not match:
        raise ValueError('请提供有效的视频链接。')
    url = match.group(0).rstrip('，。；,;')
    host = (urlparse(url).hostname or '').lower()
    platform = next((name for name, domains in {
        'douyin': ['douyin.com', 'iesdouyin.com'], 'bilibili': ['bilibili.com', 'b23.tv'],
        'youtube': ['youtube.com', 'youtu.be'], 'kuaishou': ['kuaishou.com', 'gifshow.com'],
    }.items() if any(host == domain or host.endswith('.' + domain) for domain in domains)), None)
    if not platform:
        raise ValueError('目前支持抖音、哔哩哔哩、YouTube、快手视频链接。')
    with LOCK, sqlite3.connect(STATE) as db:
        row = db.execute('SELECT url, task FROM requests WHERE id=?', (request_id,)).fetchone()
        if row:
            if row[0] != url:
                raise ValueError('请求编号与视频链接不一致。')
            return {'task_id': row[1], 'error': ''}
        # Supply a stable ID so a retry does not silently create an unrelated task.
        task = str(uuid.uuid4())
        upstream('generate_note', {
            'task_id': task, 'video_url': url, 'video_name': video_name, 'platform': platform, 'quality': 'fast',
            'provider_id': 'ollama', 'model_name': 'qwen3:8b', 'style': '简洁',
            'format': [], 'screenshot': False, 'link': False, 'video_understanding': False,
            'extras': '简洁记录视频内容。',
        })
        db.execute('INSERT INTO requests VALUES (?, ?, ?)', (request_id, url, task))
        return {'task_id': task, 'error': ''}


def poll(task):
    task = str(uuid.UUID(task))
    deadline = time.monotonic() + 20
    while True:
        data = upstream('task_status/' + task)
        status = data.get('status', '')
        if status == 'SUCCESS':
            transcript = (data.get('result') or {}).get('transcript') or {}
            if not isinstance(transcript, dict):
                raise ValueError('BiliNote 转录格式无法识别。')
            segments = transcript.get('segments') or []
            text = '\n'.join(str(segment.get('text') or '').strip()
                             for segment in segments if isinstance(segment, dict) and segment.get('text'))
            text = text.strip() or str(transcript.get('full_text') or '').strip()
            if not text:
                raise ValueError('视频处理完成，但没有可用的原始口播转录。')
            return {'done': 1, 'transcript': text, 'error': '', 'status': status}
        if status == 'FAILED':
            raise ValueError(data.get('message') or '视频转录失败。')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'done': 0, 'transcript': '', 'error': '', 'status': status}
        time.sleep(min(2, remaining))


def save_copy(payload):
    request_id = str(uuid.UUID(payload['request_id']))
    product_name = str(payload.get('product_name') or '').strip()
    video_name = str(payload.get('video_name') or '').strip()
    if not video_name or len(video_name) > 120:
        raise ValueError('请填写视频名称（最多120字）。')
    content = str(payload.get('content') or '').strip()
    if not product_name or len(product_name) > 120:
        raise ValueError('请填写产品名字（最多120字）。')
    if not content:
        raise ValueError('文案正文为空，未保存。')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', '_', product_name).strip(' .')
    if not name:
        raise ValueError('产品名字不能仅包含文件名特殊字符。')
    reference = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', '_', video_name).strip(' .')
    if not reference:
        raise ValueError('视频名称不能仅包含文件名特殊字符。')
    # Leave room for the date, separators, extension and duplicate suffix.
    name = name.encode('utf-8')[:110].decode('utf-8', errors='ignore')
    reference = reference.encode('utf-8')[:110].decode('utf-8', errors='ignore')
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    content += '\n'
    with LOCK, sqlite3.connect(STATE) as db:
        row = db.execute('SELECT filename, content FROM exports WHERE id=?', (request_id,)).fetchone()
        if row:
            if row[1] != content:
                raise ValueError('同一请求的文案内容发生变化，请重新运行流程。')
            if not (COPY_DIR / row[0]).is_file():
                raise ValueError('先前保存的文案文件已被移动或删除，请重新运行流程。')
            return {'filename': row[0], 'path': HOST_COPY_DIR + '/' + row[0], 'error': ''}
        for number in range(1, 10000):
            suffix = '' if number == 1 else f'_{number}'
            filename = f'{today}_{name}__参照{reference}{suffix}.md'
            try:
                with (COPY_DIR / filename).open('x', encoding='utf-8') as output:
                    output.write(content)
            except FileExistsError:
                continue
            db.execute('INSERT INTO exports VALUES (?, ?, ?)', (request_id, filename, content))
            return {'filename': filename, 'path': HOST_COPY_DIR + '/' + filename, 'error': ''}
        raise ValueError('同名文件数量过多，请调整产品名字。')


base_start = start
base_save = save_copy
base_poll = poll

def poll(task):
    result = base_poll(task)
    if result.get("transcript"):
        result["transcript"] = SIMPLIFIED.convert(result["transcript"])
    return result



def canonical_url(raw):
    match = re.search(r'https?://[^\s<>]+', raw)
    if not match:
        raise ValueError('请提供视频链接。')
    url = match.group(0).rstrip('，。；,;')
    parsed = urlparse(url)
    domains = ['douyin.com', 'iesdouyin.com', 'bilibili.com', 'b23.tv', 'youtube.com', 'youtu.be', 'kuaishou.com', 'gifshow.com']
    if not any(parsed.hostname == d or (parsed.hostname or '').endswith('.' + d) for d in domains):
        raise ValueError('不支持的视频平台。')
    if parsed.hostname in ['v.douyin.com', 'b23.tv', 'v.kuaishou.com']:
        try:
            with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=10) as response:
                url = response.url
            parsed = urlparse(url)
        except Exception:
            pass  # A failed short-link expansion must not prevent BiliNote from trying.
    host = parsed.hostname or ''
    query = parse_qs(parsed.query)
    if 'douyin.com' in host:
        match = re.search(r'/video/(\d+)', parsed.path)
        vid = match.group(1) if match else (query.get('modal_id') or query.get('vid') or [''])[0]
        if vid: return 'douyin:' + vid, 'https://www.douyin.com/video/' + vid
    if 'bilibili.com' in host:
        match = re.search(r'/video/([^/]+)', parsed.path)
        if match: return 'bilibili:' + match.group(1), url
    if 'youtu' in host:
        vid = (query.get('v') or [''])[0] or (parsed.path.strip('/') if host == 'youtu.be' else '')
        if vid: return 'youtube:' + vid, 'https://www.youtube.com/watch?v=' + vid
    if 'kuaishou.com' in host:
        match = re.search(r'/short-video/([^/]+)', parsed.path)
        if match: return 'kuaishou:' + match.group(1), url
    return host + parsed.path + ('?' + parsed.query if parsed.query else ''), url


def existing_video(key):
    with sqlite3.connect(STATE) as db:
        row = db.execute('SELECT task FROM videos WHERE key=?', (key,)).fetchone()
    if row:
        try:
            data = upstream('task_status/' + row[0])
            if data.get('status') != 'FAILED': return row[0]
        except Exception:
            pass
    # Reuse completed notes already created in BiliNote, without renaming them.
    for path in sorted(Path('/bilinote-data/note_results').glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True):
        try:
            task = str(uuid.UUID(path.stem))
            result = json.loads(path.read_text())
            meta = result.get('audio_meta') or {}
            if meta.get('platform', '') + ':' + str(meta.get('video_id', '')) == key and result.get('transcript') and result.get('markdown'):
                return task
        except (ValueError, OSError, AttributeError):
            continue
    return ''


def start(payload):
    key, url = canonical_url(payload.get('video_url', ''))
    mode = payload.get('cache_mode') or '自动复用（失败续跑）'
    material = {k:payload.get(k) for k in ['video_name','product_name','product_text','product_files','extra_requirements','pipeline_version']}
    material['video'] = key
    fingerprint = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with LOCK, sqlite3.connect(STATE) as db:
        row = db.execute('SELECT id, completed FROM jobs WHERE fingerprint=?', (fingerprint,)).fetchone()
        job = row[0] if row and row[1] == 0 and mode == '自动复用（失败续跑）' else str(uuid.uuid4())
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?, 0)', (fingerprint, job))
    # A retry of an unfinished job reuses its original video task even in forced mode.
    with sqlite3.connect(STATE) as db:
        taskrow = db.execute('SELECT task FROM requests WHERE id=?', (job,)).fetchone()
    task = taskrow[0] if taskrow else ''
    if task:
        try:
            if upstream('task_status/' + task).get('status') == 'FAILED': task = ''
        except Exception:
            task = ''
        if not task:
            with sqlite3.connect(STATE) as db:
                db.execute('DELETE FROM requests WHERE id=?', (job,))
    if not task and mode != '重新处理视频': task = existing_video(key)
    if not task:
        result = base_start({**payload, 'video_url':url, 'request_id':job})
        task = result['task_id']
    else:
        with sqlite3.connect(STATE) as db:
            db.execute('INSERT OR REPLACE INTO requests VALUES (?, ?, ?)', (job, url, task))
    with sqlite3.connect(STATE) as db:
        db.execute('INSERT OR REPLACE INTO videos VALUES (?, ?)', (key, task))
    return {'task_id':task, 'job_id':job, 'mode':mode, 'error':''}


def cache_get(payload):
    jobkey = 'job:' + str(uuid.UUID(payload['job_id'])) + ':' + payload['key']
    globalkey = 'global:' + payload['key']
    forced = payload.get('mode') in ['重新分析原型','重新处理视频']
    with sqlite3.connect(STATE) as db:
        row = db.execute('SELECT value FROM cache WHERE key=?', (jobkey,)).fetchone()
        if not row and payload['stage'] in ['analysis','facts'] and not forced:
            row = db.execute('SELECT value FROM cache WHERE key=?', (globalkey,)).fetchone()
    return {'hit':1 if row else 0, 'text':row[0] if row else '', 'error':''}


def cache_put(payload):
    value = str(payload.get('text') or '').strip()
    if not value: raise ValueError('阶段结果为空，未写入缓存。')
    jobkey = 'job:' + str(uuid.UUID(payload['job_id'])) + ':' + payload['key']
    with sqlite3.connect(STATE) as db:
        db.execute('INSERT OR REPLACE INTO cache VALUES (?, ?)', (jobkey, value))
        if payload['stage'] in ['analysis','facts']:
            db.execute('INSERT OR REPLACE INTO cache VALUES (?, ?)', ('global:' + payload['key'], value))
    return {'text':value, 'error':''}


def save_copy(payload):
    content = SIMPLIFIED.convert(str(payload.get("content") or ""))
    result = base_save({**payload, "content": content})
    result["text"] = content
    with sqlite3.connect(STATE) as db:
        db.execute('UPDATE jobs SET completed=1 WHERE id=?', (payload['request_id'],))
    return result


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 262144:
                raise ValueError('请求大小无效。')
            payload = json.loads(self.rfile.read(size))
            if self.path == '/start':
                result = start(payload)
            elif self.path == '/cache-get':
                result = cache_get(payload)
            elif self.path == '/cache-put':
                result = cache_put(payload)
            elif self.path == '/save-copy':
                result = save_copy(payload)
            elif self.path == '/poll':
                result = poll(payload['task_id'])
            else:
                raise ValueError('未知接口。')
        except Exception as error:
            result = {'task_id': '', 'done': 1, 'transcript': '', 'status': 'FAILED', 'error': str(error)}
        encoded = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
