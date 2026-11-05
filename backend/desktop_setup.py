"""First-run desktop setup. Bundled rules are separate from personal Codex skills."""
import json
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import threading
import zipfile
from contextlib import closing

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import core

router = APIRouter()
LOCK = threading.Lock()


def require_desktop():
    if not core.STANDALONE:
        raise HTTPException(404, '此入口仅用于独立运行模式')


def initialize():
    """Copy only shipped author rules; never inspect the author's private data."""
    require_desktop()
    source = core.ROOT / 'config/author-skills/pipi-copywriting'
    target = core.SKILLS / 'pipi-copywriting'
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    card = core.DATA / 'authors/xupp141010/writing-card.json'
    if not card.exists():
        card.parent.mkdir(parents=True, exist_ok=True)
        metadata = json.loads((source / 'card.json').read_text())
        card.write_text(core.dumps({**metadata, 'corpus_usable_count': 0, 'skill_path': str(target / 'SKILL.md')}))
        card.chmod(0o600)
    if not core.CONFIG.exists():
        core.save_settings({})
    core.init_db()


def completed():
    path = core.DATA / 'desktop-setup.json'
    try:
        return json.loads(path.read_text()).get('completed', False)
    except (OSError, ValueError, AttributeError):
        return False


def finish():
    path = core.DATA / 'desktop-setup.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(core.dumps({'completed': True, 'updated_at': core.now()}))
    temporary.chmod(0o600)
    temporary.replace(path)


@router.get('/status')
def status():
    if not core.STANDALONE:
        return {'enabled': False}
    cfg = core.settings()
    names = []
    connected = False
    try:
        with httpx.Client(trust_env=False, timeout=2) as client:
            response = client.get(core.local_url(cfg['ollama_url']) + '/api/tags')
            response.raise_for_status()
            names = [m['name'] for m in response.json().get('models', [])]
            connected = True
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    from . import author_profiles
    if core.DESKTOP:
        from . import desktop_ai
        ai_status = desktop_ai.MANAGER.status() if desktop_ai.MANAGER else {'bundled': False}
    else:
        from . import local_setup
        ai_status = local_setup.status()
    return {'enabled': True, 'completed': completed(), 'data_path': str(core.DATA),
            'host': 'desktop' if core.DESKTOP else 'web', 'ai': ai_status,
            'tools': {name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe', 'pdftoppm')},
            'ollama': connected, 'text_model': cfg['text_model'], 'text_installed': cfg['text_model'] in names,
            'vision_model': cfg['vision_model'], 'vision_installed': cfg['vision_model'] in names,
            'whisper': (Path(cfg['whisper_model']) / 'model.bin').is_file(),
            'authors': [a['name'] for a in author_profiles.catalog()],
            'empty': not any(core.records(k) for k in ('case', 'product', 'draft'))}


class SetupInput(BaseModel):
    demo: bool = False


@router.post('/ai/restart')
def restart_ai():
    require_desktop()
    if not core.DESKTOP:
        from . import local_setup
        return local_setup.begin()
    from . import desktop_ai
    with LOCK:
        with core.db() as con:
            if con.execute("SELECT count(*) FROM tasks WHERE status IN ('queued','running')").fetchone()[0]:
                raise ValueError('请先等待当前任务结束，再重新启动 AI')
        manager = desktop_ai.MANAGER
        if manager is None: raise ValueError('此安装包未包含内置 AI，请使用完整离线包')
        manager.close()
        desktop_ai.start(manager.pack)
        return desktop_ai.MANAGER.status()


@router.post('/ai/prepare')
def prepare_ai():
    require_desktop()
    from . import local_setup
    return local_setup.begin()


@router.post('/complete')
def complete(data: SetupInput):
    require_desktop()
    with LOCK:
        if data.demo:
            if completed():
                raise ValueError('已经完成首次设置，未重复写入演示资料')
            if any(core.records(k) for k in ('case', 'product', 'draft')):
                raise ValueError('资料库已有内容，请直接进入工作台；演示资料只用于空库')
            from . import jobs, media
            directory = core.media_root() / 'demo-video'
            directory.mkdir(parents=True, exist_ok=True)
            video = directory / 'sample.mp4'
            media.command(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                           'color=c=0x405844:s=640x360:d=2', '-c:v', 'mpeg4', str(video)])
            info, frames, _ = media.extract(video, lambda *args: None)
            case = core.put('case', {'title': '从真实资料开始 · 演示视频', 'platform': '演示',
                'category': '使用示例', 'tags': ['演示数据'], 'metrics': {},
                'video': str(video.relative_to(core.media_root())), 'frames': frames,
                'cover': frames[0]['path'], 'processing_status': 'frames_ready', **info})
            jobs.save_transcript(case, '这是人工提供的演示逐字稿。先展示产品细节，再说明适用场景。')
            jobs.case_note(core.get(case['id']))
            note = core.sync_note('产品资料', 'demo-canvas-bag', '示例帆布袋',
                                  '虚构演示资料：米白色、短提手、内侧拉链小袋。价格、容量、承重未知。')
            product = core.put('product', {'name': '示例帆布袋 · 演示数据', 'note': note, 'files': []})
            jobs.draft_version(case['id'], product['id'], '这是一份人工提供的演示文案，并非 AI 生成结果。\n\n米白色帆布袋，配短提手，内侧有拉链小袋。\n价格、容量和承重还需要确认。')
        finish()
    return {'completed': True}


def import_backup(path):
    """Offline import into an empty desktop library; do not import paths or keys.

    The launcher stops its own backend first; backend_entry holds desktop.lock.
    All checks and extraction happen before replacing the empty destination DB.
    """
    require_desktop()
    cfg = core.settings()
    vault = Path(cfg['vault_path']).resolve()
    media = core.media_root()
    with core.db() as con:
        if con.execute('SELECT count(*) FROM records').fetchone()[0] or con.execute('SELECT count(*) FROM tasks').fetchone()[0]:
            raise ValueError('只能导入到空资料库；已有内容未改动')
    if any(p.is_file() for root in (vault, media) for p in root.rglob('*')):
        raise ValueError('资料目录已有文件；为保留现有内容，未执行导入')
    with tempfile.TemporaryDirectory(dir=core.DATA, prefix='import-') as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            if len(names) != len(set(names)) or len(entries) > 100000:
                raise ValueError('备份包含重复或过多条目')
            if sum(e.file_size for e in entries) > min(20 * 1024**3, shutil.disk_usage(core.DATA).free // 2):
                raise ValueError('备份过大或可用空间不足')
            for entry in entries:
                item = Path(entry.filename)
                if item.is_absolute() or '..' in item.parts or '\\' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError('备份含不安全路径')
                if entry.filename not in ('manifest.json', 'data/virallab.sqlite3', 'data/settings.json') and not entry.filename.startswith(('notes/', 'media/', 'dify-workflows/')):
                    raise ValueError('备份包含未知条目')
            if not {'manifest.json', 'data/virallab.sqlite3'}.issubset(names):
                raise ValueError('不是 ViralLab 备份')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('version') != 1 or manifest.get('vault_subdir') != cfg['vault_subdir']:
                raise ValueError('此备份版本或笔记目录暂不支持导入')
            archive.extractall(stage)
        database = stage / 'data/virallab.sqlite3'
        with closing(sqlite3.connect(database)) as con:
            con.execute('PRAGMA journal_mode=DELETE')
            if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('备份数据库已损坏')
            if con.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:
                raise ValueError('备份包含不支持的数据库结构')
            for table, columns in {'records': {'id','kind','body','created_at','updated_at'},
                                   'tasks': {'id','kind','status','stage','progress','payload'},
                                   'note_sync': {'relative','hash'}}.items():
                if not columns.issubset({r[1] for r in con.execute(f'PRAGMA table_info({table})')}):
                    raise ValueError('备份数据库格式不兼容')
            for body, in con.execute('SELECT body FROM records'):
                json.loads(body)
            # Imported unfinished tasks must not silently resume against new services.
            con.execute("UPDATE tasks SET status='interrupted', stage='从备份导入，请核对模型与资料后重试' WHERE status IN ('queued','running')")
            con.commit()
        old_db = stage / 'empty.sqlite3'
        with core.db() as source, closing(sqlite3.connect(old_db)) as target:
            source.backup(target)
        copied = []
        try:
            for prefix, target in [('media', media), ('notes', core.contained(vault, cfg['vault_subdir']))]:
                for source in (stage / prefix).rglob('*'):
                    if not source.is_file():
                        continue
                    destination = core.contained(target, source.relative_to(stage / prefix))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                    copied.append(destination)
            for suffix in ('-wal', '-shm'):
                (core.DATA / ('virallab.sqlite3' + suffix)).unlink(missing_ok=True)
            database.replace(core.DATA / 'virallab.sqlite3')
            core.repair_note_uris()
            finish()
        except Exception:
            for suffix in ('-wal', '-shm'):
                (core.DATA / ('virallab.sqlite3' + suffix)).unlink(missing_ok=True)
            shutil.copyfile(old_db, core.DATA / 'virallab.sqlite3')
            for destination in copied:
                destination.unlink(missing_ok=True)
            raise
