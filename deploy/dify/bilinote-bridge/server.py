"""Local BiliNote adapter. Dify controls the polling loop and all copywriting."""
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

UPSTREAM = os.getenv('BILINOTE_URL', 'http://host.docker.internal:18080').rstrip('/')
STATE = Path('/data/requests.sqlite3')
STATE.parent.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
COPY_DIR = Path('/obsidian-copy')
HOST_COPY_DIR = os.getenv('HOST_COPY_DIR', '/obsidian-copy')
with sqlite3.connect(STATE) as db:
    db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, url TEXT NOT NULL, task TEXT NOT NULL)')
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
    content = str(payload.get('content') or '').strip()
    if not product_name or len(product_name) > 120:
        raise ValueError('请填写产品名字（最多120字）。')
    if not content:
        raise ValueError('文案正文为空，未保存。')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', '_', product_name).strip(' .')
    if not name:
        raise ValueError('产品名字不能仅包含文件名特殊字符。')
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
            filename = f'{today}_{name}_文案{suffix}.md'
            try:
                with (COPY_DIR / filename).open('x', encoding='utf-8') as output:
                    output.write(content)
            except FileExistsError:
                continue
            db.execute('INSERT INTO exports VALUES (?, ?, ?)', (request_id, filename, content))
            return {'filename': filename, 'path': HOST_COPY_DIR + '/' + filename, 'error': ''}
        raise ValueError('同名文件数量过多，请调整产品名字。')


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 262144:
                raise ValueError('请求大小无效。')
            payload = json.loads(self.rfile.read(size))
            if self.path == '/start':
                result = start(payload)
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
