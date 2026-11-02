"""Readable Obsidian paths and the same collection/research boundary as the UI."""
from pathlib import Path
from . import core

RESEARCH_NAMES={'video':'文案研究','title':'标题研究','cover':'封面提示词','cover_visual':'封面研究','compare':'案例对比','suggest':'标题建议'}
FOLDERS=('已收录视频','研究所/案例','研究所/文案研究','研究所/标题研究','研究所/封面提示词','研究所/封面研究','研究所/案例对比','研究所/标题建议','原创文案','产品资料','历史保留')

def case_folder(id):
    return '研究所/案例' if any(a.get('case_id')==id for a in core.records('analysis')) else '已收录视频'

def analysis_location(a):
    name=RESEARCH_NAMES.get(a.get('type'),'其他研究')
    if a.get('type')=='cover' and not a.get('result',{}).get('可复制的封面提示词'):name='历史封面研究'
    try:label=core.get(a.get('case_id'),'case')['title'] if a.get('case_id') else '独立研究'
    except ValueError:label='历史案例'
    return '研究所/'+name,name+' · '+label

def draft_title(d):
    if (d.get('title') or '').strip():return d['title'].strip()
    try:label=core.get(d.get('case_id'),'case')['title']
    except ValueError:label='历史案例'
    return '原创文案 · '+label

def migrate():
    """Only move notes owned by ViralLab. Keep every body, including human edits."""
    moves=[]
    def move(relative,folder,id,title):
        if not relative:return
        target=core.note_relative(folder,id,title)
        if relative!=target:
            core.relocate_note(relative,target,title)
            moves.append((relative,target))
    for c in core.records('case')+core.records('archived_case'):
        folder='历史保留/已删除素材' if c['kind']=='archived_case' else case_folder(c['id'])
        move(c.get('note',{}).get('path'),folder,c['id'],c['title'])
        move(c.get('transcript_note'),folder,c['id']+'-transcript',c['title']+' · 口播逐字稿')
    for a in core.records('analysis'):
        folder,title=analysis_location(a)
        move((a.get('note') or {}).get('path'),folder,a['id'],title)
    for d in core.records('draft'):
        move((d.get('note') or {}).get('path'),'原创文案',d['id'],draft_title(d))
    for p in core.records('product'):
        move((p.get('note') or {}).get('path'),'产品资料',p['id'],p.get('name','产品资料'))
    return moves

def refresh_indexes():
    """Small generated navigation pages, confined to the authorized subtree."""
    cfg=core.settings();root=core.contained(cfg['vault_path'],cfg['vault_subdir'])
    links=[]
    for folder in ('已收录视频','研究所','原创文案','产品资料','历史保留'):
        files=sorted((root/folder).rglob('*.md')) if (root/folder).exists() else []
        rows=[]
        for p in files:
            if '--index-' in p.name:continue
            relative=str(p.relative_to(Path(cfg['vault_path'])))
            rows.append('- [['+relative[:-3]+'|'+p.stem.split('--')[0]+']]')
        note=core.sync_note(folder,'index-'+folder,folder,'# '+folder+'\n\n'+('\n'.join(rows) or '暂无内容。'))
        links.append('- [['+note['path'][:-3]+'|'+folder+']]')
    core.sync_note('','virallab-index','ViralLab 工作台','# ViralLab 工作台\n\n'+ '\n'.join(links)+'\n\n已收录视频仅保存未研究素材；至少完成一项研究后进入研究所。标题研究包含原视频发布标题、发布文案和话题标签。')
