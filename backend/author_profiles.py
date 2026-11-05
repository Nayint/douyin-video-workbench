"""Load registered, installed author skills; never accept a skill path from a request."""
import hashlib
import json
import re
from pathlib import Path
from . import core

MODES = ('生活分享', '直接推荐', '演示答疑')
SKILLS_ROOT = core.SKILLS


def load(author_id):
    for path in (core.DATA / 'authors').glob('*/writing-card.json'):
        try:
            card = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if card.get('author_id') != author_id:
            continue
        skill = Path(card.get('skill_path') or '').resolve()
        if skill.name != 'SKILL.md' or not skill.is_relative_to(SKILLS_ROOT.resolve()) or not skill.is_file():
            raise ValueError('作者写作卡的Skill文件不可用，请重新登记作者卡')
        text = skill.read_text()
        if len(text) > 20000:
            raise ValueError('作者Skill过长，请精简后再使用')
        version = re.search(r'版本：[ `]*([\d.]+)', text)
        return {'id': author_id, 'name': card['display_name'],
                'version': version.group(1).rstrip('.') if version else card.get('version', ''),
                'skill_hash': hashlib.sha256(text.encode()).hexdigest(), 'instructions': text,
                'modes': list(MODES), 'source_count': card.get('corpus_usable_count', 0)}
    raise ValueError('作者写作卡不存在，请重新选择作者')


def public(profile):
    return {k: profile[k] for k in ('id', 'name', 'version', 'skill_hash', 'modes', 'source_count')}


def catalog():
    result = []
    for path in sorted((core.DATA / 'authors').glob('*/writing-card.json')):
        try:
            card = json.loads(path.read_text())
            result.append(public(load(card.get('author_id'))))
        except (ValueError, OSError, KeyError):
            continue
    return result
