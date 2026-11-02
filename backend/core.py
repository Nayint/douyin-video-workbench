"""Local configuration, SQLite records and constrained Obsidian access."""
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from .cover_rules import DEFAULT_STYLE
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('VIRALLAB_DATA', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
CONFIG = DATA / 'settings.json'
DEFAULTS = dict(ollama_url='http://127.0.0.1:11434', text_model='qwen3:8b', vision_model='qwen3-vl:8b-instruct',
    dify_url='http://127.0.0.1:8081/v1', dify_keys={}, bilinote_url='http://127.0.0.1:18080',
    vault_path=str(Path.home() / 'Documents' / 'ViralLabVault'), vault_subdir='ViralLab',
    product_subdir='ViralLab/产品资料', storage_path=str(DATA / 'media'),
    whisper_model=str(Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120'),
    max_upload_mb=500, frame_count=8, model_timeout=600,
    cover_style_profile=DEFAULT_STYLE)
CONFIG_LOCK = threading.RLock()
NOTE_LOCK = threading.RLock()

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def dumps(v): return json.dumps(v, ensure_ascii=False)
def settings():
    with CONFIG_LOCK:
        return {**DEFAULTS, **(json.loads(CONFIG.read_text()) if CONFIG.exists() else {})}
def save_settings(values):
    with CONFIG_LOCK:
        cfg = {**settings(), **values}
        tmp = CONFIG.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f: f.write(dumps(cfg))
        tmp.replace(CONFIG)
        return cfg

def contained(root, relative):
    root = Path(root).resolve()
    p = (root / relative).resolve()
    if p == root or not p.is_relative_to(root): raise ValueError('文件路径必须位于授权目录内')
    return p

def local_url(raw):
    u = urlparse(raw)
    if u.scheme != 'http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.query or u.fragment:
        raise ValueError('服务地址仅支持本机 HTTP 地址；不允许云端或带凭据的 URL')
    return raw.rstrip('/')

@contextmanager
def db():
    con = sqlite3.connect(DATA / 'virallab.sqlite3', timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback(); raise
    finally: con.close()

def init_db():
    with db() as con:
        con.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS records_kind ON records(kind,updated_at);
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, resource_id TEXT, payload TEXT NOT NULL,
          status TEXT NOT NULL, stage TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
          error TEXT, result TEXT, run_id TEXT, remote_task_id TEXT,
          request_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS note_sync (relative TEXT PRIMARY KEY, hash TEXT NOT NULL);
        ''')
        if 'dismissed_at' not in {row[1] for row in con.execute('PRAGMA table_info(tasks)')}:
            con.execute('ALTER TABLE tasks ADD COLUMN dismissed_at TEXT')
        con.execute("UPDATE tasks SET status='interrupted', stage='服务重启，任务已中断；Dify 任务请先查询运行状态' WHERE status='running'")

def put(kind, body, id=None):
    id = id or uid(); stamp=now()
    with db() as con:
        old=con.execute('SELECT created_at FROM records WHERE id=?',(id,)).fetchone()
        con.execute('INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at',
            (id,kind,dumps(body),old[0] if old else stamp,stamp))
    return get(id,kind)

def get(id, kind=None):
    with db() as con: row=con.execute('SELECT * FROM records WHERE id=?',(id,)).fetchone()
    if not row or (kind and row['kind']!=kind): raise ValueError('记录不存在')
    return {**json.loads(row['body']), 'id':row['id'],'kind':row['kind'],'created_at':row['created_at'],'updated_at':row['updated_at']}

def records(kind):
    with db() as con: rows=con.execute('SELECT * FROM records WHERE kind=? ORDER BY updated_at DESC',(kind,)).fetchall()
    return [{**json.loads(r['body']),'id':r['id'],'kind':r['kind'],'created_at':r['created_at'],'updated_at':r['updated_at']} for r in rows]

def update_record(id, changes):
    old=get(id); return put(old['kind'],{**old,**changes},id)

def media_root():
    p=Path(settings()['storage_path']).expanduser().resolve(); p.mkdir(parents=True,exist_ok=True,mode=0o700); return p

def note_read(relative):
    cfg=settings(); return contained(cfg['vault_path'],relative).read_text(encoding='utf-8')

def obsidian_uri(relative):
    path=contained(settings()['vault_path'],relative)
    return 'obsidian://open?path='+quote(str(path),safe='')

def repair_note_uris():
    def repair(value):
        if isinstance(value,list):return [repair(v) for v in value]
        if isinstance(value,dict):
            value={k:repair(v) for k,v in value.items()}
            if isinstance(value.get('uri'),str) and value['uri'].startswith('obsidian://') and value.get('path'):
                value['uri']=obsidian_uri(value['path'])
            return value
        return value
    with db() as c:
        for row in c.execute('SELECT id,body FROM records').fetchall():
            body=json.loads(row['body']);updated=repair(body)
            if updated!=body:c.execute('UPDATE records SET body=? WHERE id=?',(dumps(updated),row['id']))
        for row in c.execute('SELECT id,result FROM tasks WHERE result IS NOT NULL').fetchall():
            body=json.loads(row['result']);updated=repair(body)
            if updated!=body:c.execute('UPDATE tasks SET result=? WHERE id=?',(dumps(updated),row['id']))

def note_relative(folder,id,title):
    import re
    name=re.sub(r'[\x00-\x1f/\\:*?"<>|#\[\]]',' ',title).strip().strip('.')[:60] or '未命名'
    return "/".join(x for x in (settings()['vault_subdir'],folder,f"{name}--{id}.md") if x)

def relocate_note(old,new,title=None):
    """Rename only; rewrite metadata title while preserving the entire note body."""
    import yaml
    cfg=settings();source=contained(cfg['vault_path'],old);target=contained(cfg['vault_path'],new)
    with NOTE_LOCK:
        if not source.exists():return
        if target.exists() and target!=source:raise ValueError('Obsidian 目标笔记已存在，未覆盖：'+new)
        original=source.read_bytes();content=original
        with db() as c:row=c.execute('SELECT hash FROM note_sync WHERE relative=?',(old,)).fetchone()
        unchanged=bool(row and hashlib.sha256(original).hexdigest()==row[0])
        if title and original.startswith(b'---\n'):
            parts=original.decode('utf-8').split('---\n',2)
            if len(parts)==3:
                front=yaml.safe_load(parts[1])
                if isinstance(front,dict):
                    front['title']=title
                    content=('---\n'+yaml.safe_dump(front,allow_unicode=True,sort_keys=False)+'---\n'+parts[2]).encode()
        target.parent.mkdir(parents=True,exist_ok=True)
        if content!=original:source.write_bytes(content)
        if source!=target:source.rename(target)
        old_uri='obsidian://open?vault='+quote(cfg['vault_path'])+'&file='+quote(old)
        new_uri=obsidian_uri(new)
        def replace(value):
            if isinstance(value,str):return new if value==old else new_uri if value in (old_uri,obsidian_uri(old)) else value
            if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
            if isinstance(value,list):return [replace(v) for v in value]
            return value
        with db() as c:
            c.execute('DELETE FROM note_sync WHERE relative=?',(old,))
            c.execute('INSERT OR REPLACE INTO note_sync VALUES(?,?)',(new,hashlib.sha256(content).hexdigest() if unchanged else 'human-modified'))
            for row in c.execute('SELECT id,body FROM records').fetchall():
                body=json.loads(row['body']);updated=replace(body)
                if updated!=body:c.execute('UPDATE records SET body=? WHERE id=?',(dumps(updated),row['id']))
            for row in c.execute('SELECT id,result FROM tasks WHERE result IS NOT NULL').fetchall():
                value=json.loads(row['result']);updated=replace(value)
                if updated!=value:c.execute('UPDATE tasks SET result=? WHERE id=?',(dumps(updated),row['id']))

def sync_note(folder, id, title, body, metadata=None):
    """Never overwrite a note edited outside ViralLab; preserve both versions."""
    import yaml
    cfg=settings(); relative=note_relative(folder,id,title)
    with db() as c:old=c.execute('SELECT relative FROM note_sync WHERE relative LIKE ?',('%/'+id+'.md',)).fetchone()
    if not old:
        with db() as c:old=c.execute('SELECT relative FROM note_sync WHERE relative LIKE ?',('%--'+id+'.md',)).fetchone()
    if old and old[0]!=relative:relocate_note(old[0],relative,title)
    path=contained(cfg['vault_path'],relative)
    with NOTE_LOCK:
        path.parent.mkdir(parents=True,exist_ok=True)
        with db() as con: row=con.execute('SELECT hash FROM note_sync WHERE relative=?',(relative,)).fetchone()
        front={'id':id,'title':title,'updated_at':now(),**(metadata or {})}
        content='---\n'+yaml.safe_dump(front,allow_unicode=True,sort_keys=False)+'---\n\n'+body+'\n'
        if path.exists() and (not row or hashlib.sha256(path.read_bytes()).hexdigest()!=row[0]):
            conflict=path.with_name(path.stem+'.conflict-'+uid()[:8]+'.md')
            conflict.write_text(content,encoding='utf-8')
            return {'path':relative,'conflict':str(conflict.relative_to(cfg['vault_path'])),'status':'conflict'}
        tmp=path.with_suffix('.tmp'); tmp.write_text(content,encoding='utf-8'); tmp.replace(path)
        with db() as con: con.execute('INSERT OR REPLACE INTO note_sync VALUES(?,?)',(relative,hashlib.sha256(path.read_bytes()).hexdigest()))
    return {'path':relative,'status':'saved','uri':obsidian_uri(relative)}
