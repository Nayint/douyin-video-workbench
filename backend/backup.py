import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from . import core

def create_backup():
    with core.db() as c:
        if c.execute("SELECT count(*) FROM tasks WHERE status IN ('queued','running')").fetchone()[0]:
            raise ValueError('请等待当前任务完成后创建一致性备份')
    directory=core.BACKUPS;directory.mkdir(exist_ok=True,mode=0o700)
    path=directory/f'virallab-{core.uid()}.zip'
    with tempfile.TemporaryDirectory(dir=core.DATA) as tmp:
        snapshot=Path(tmp)/'virallab.sqlite3'
        with core.db() as src,sqlite3.connect(snapshot) as dest:src.backup(dest)
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot,'data/virallab.sqlite3')
            if core.CONFIG.exists():z.write(core.CONFIG,'data/settings.json')
            for p in (core.DATA/'dify-model-backups').glob('*.yml'):
                if p.is_file() and not p.is_symlink():z.write(p,'dify-workflows/'+p.name)
            for p in core.media_root().rglob('*'):
                if p.is_file() and not p.is_symlink():z.write(p,'media/'+str(p.relative_to(core.media_root())))
            cfg=core.settings();vault=core.contained(cfg['vault_path'],cfg['vault_subdir'])
            if vault.exists():
                for p in vault.rglob('*.md'):
                    if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(vault):z.write(p,'notes/'+str(p.relative_to(vault)))
            z.writestr('manifest.json',core.dumps({'version':1,'created_at':core.now(),'vault_subdir':cfg['vault_subdir']}))
    path.chmod(0o600);return path

def restore_backup(path):
    """Offline restore, preflight all entries; keep existing notes as conflict copies."""
    # Stop script holds no DB connection; refuse while local HTTP service responds.
    import socket
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',8765))==0:raise ValueError('请先停止 ViralLab 再恢复')
    cfg=core.settings();note_root=core.contained(cfg['vault_path'],cfg['vault_subdir'])
    with zipfile.ZipFile(path) as z:
        entries=z.infolist()
        if sum(e.file_size for e in entries)>100*1024**3:raise ValueError('备份展开超过 100 GB')
        if not {'manifest.json','data/virallab.sqlite3'}.issubset(z.namelist()):raise ValueError('不是 ViralLab 备份')
        for e in entries:
            p=Path(e.filename)
            if p.is_absolute() or '..' in p.parts or (e.external_attr>>16)&0o170000==0o120000:raise ValueError('备份含不安全路径')
            if e.filename not in ('manifest.json','data/virallab.sqlite3','data/settings.json') and not e.filename.startswith(('media/','notes/','dify-workflows/')):raise ValueError('备份含未知条目')
        before=create_backup()
        with tempfile.TemporaryDirectory(dir=core.DATA) as tmp:
            z.extractall(tmp);stage=Path(tmp)
            with sqlite3.connect(stage/'data/virallab.sqlite3') as c:
                if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('备份数据库完整性检查失败')
            for prefix,root in [('media',core.media_root()),('notes',note_root),('dify-workflows',core.DATA/'dify-model-backups')]:
                source=stage/prefix
                if not source.exists():continue
                for p in source.rglob('*'):
                    if not p.is_file():continue
                    dest=core.contained(root,p.relative_to(source));dest.parent.mkdir(parents=True,exist_ok=True)
                    if dest.exists() and dest.read_bytes()!=p.read_bytes():
                        if prefix=='media':
                            preserved=dest.with_name(dest.stem+'.before-restore-'+core.uid()[:8]+dest.suffix)
                            shutil.copyfile(dest,preserved);shutil.copyfile(p,dest);continue
                        dest=dest.with_name(dest.stem+'.restore-'+core.uid()[:8]+dest.suffix)
                    if not dest.exists():shutil.copyfile(p,dest)
            # Preserve current machine paths. Import credentials only when explicitly restoring config.
            shutil.copyfile(stage/'data/virallab.sqlite3',core.DATA/'virallab.sqlite3')
            for suffix in ('-wal','-shm'):(core.DATA/('virallab.sqlite3'+suffix)).unlink(missing_ok=True)
            if not core.CONFIG.exists() and (stage/'data/settings.json').exists():
                restored=json.loads((stage/'data/settings.json').read_text())
                core.save_settings({'dify_keys':restored.get('dify_keys',{})})
    return str(before)
