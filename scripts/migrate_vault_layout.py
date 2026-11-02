"""Run with ViralLab stopped. Back up before renaming only authorized notes."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import core,note_layout
from backend.backup import create_backup

backup=create_backup()
cfg=core.settings();root=core.contained(cfg['vault_path'],cfg['vault_subdir'])
before={p:p.read_text().split('---\n',2)[-1] for p in root.rglob('*.md') if p.is_file()}
moves=note_layout.migrate()
# Preserve old conflict copies and any unmanaged note inside obsolete directories.
for folder in ('视频案例','标题研究','封面研究','爆款规律','创作文案','产品关联','账号研究'):
    old=root/folder
    if not old.exists():continue
    for p in list(old.rglob('*.md')):
        target=root/'历史保留'/folder/p.relative_to(old)
        if target.exists():raise ValueError('历史笔记目标已存在，停止迁移')
        core.relocate_note(str(p.relative_to(cfg['vault_path'])),str(target.relative_to(cfg['vault_path'])))
        moves.append((str(p.relative_to(cfg['vault_path'])),str(target.relative_to(cfg['vault_path']))))
    for directory in sorted([p for p in old.rglob('*') if p.is_dir()],reverse=True)+[old]:
        if not any(directory.iterdir()):directory.rmdir()
if cfg['product_subdir']==cfg['vault_subdir']+'/产品关联':core.save_settings({'product_subdir':cfg['vault_subdir']+'/产品资料'})
for folder in note_layout.FOLDERS:(root/folder).mkdir(parents=True,exist_ok=True)
# Every moved note body, including human edits, must be byte-for-byte identical as text.
for source,target in moves:
    previous=before.get(core.contained(cfg['vault_path'],source))
    if previous is not None:
        assert core.contained(cfg['vault_path'],target).read_text().split('---\n',2)[-1]==previous
note_layout.refresh_indexes()
report={'backup':str(backup),'moves':moves,'verified_note_bodies':len(moves),'created_at':core.now()}
(core.DATA/'vault-layout-migration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'backup':str(backup),'moved_notes':len(moves),'body_verification':'passed'},ensure_ascii=False))
