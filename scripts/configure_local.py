"""Configure local models, Dify application ID/key and bundled author card."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import core, author_profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text-model')
    parser.add_argument('--vision-model')
    parser.add_argument('--whisper-model', type=Path)
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--prototype-app-id')
    parser.add_argument('--link-app-id')
    parser.add_argument('--install-author', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    values = {}
    for field in ('text_model','vision_model'):
        if getattr(args, field): values[field] = getattr(args, field)
    if args.whisper_model:
        model=args.whisper_model.expanduser().resolve()
        if not (model/'model.bin').is_file(): parser.error('转写目录缺少 model.bin')
        values['whisper_model']=str(model)
    if args.vault:
        vault=args.vault.expanduser().resolve();vault.mkdir(parents=True,exist_ok=True)
        values['vault_path']=str(vault)
    keys = dict(core.settings()['dify_keys'])
    for mode in ('prototype','link'):
        app_id=getattr(args,mode+'_app_id')
        if app_id:
            try: app_id=str(UUID(app_id))
            except ValueError: parser.error('Dify application ID must be a UUID')
            key=getpass.getpass(f'{mode} API Key（隐藏输入；留空保留已存密钥）: ').strip()
            previous=keys.get(mode,{})
            if not key and previous.get('app_id') != app_id:
                parser.error('新应用必须填写对应的新 API Key')
            keys[mode]={'app_id':app_id,'api_key':key or previous.get('api_key','')}
    if args.prototype_app_id or args.link_app_id: values['dify_keys']=keys
    if args.install_author:
        source=core.ROOT/'config/author-skills/pipi-copywriting'
        target=author_profiles.SKILLS_ROOT/'pipi-copywriting'
        # Do not overwrite an existing custom skill, even on a rerun.
        if target.exists():
            if not (target/'SKILL.md').is_file() or (target/'SKILL.md').read_bytes() != (source/'SKILL.md').read_bytes():
                parser.error('本机已有不同版本作者 Skill，保留原文件；请先自行审阅')
        else: shutil.copytree(source,target)
        directory=core.DATA/'authors'/'xupp141010';directory.mkdir(parents=True,exist_ok=True)
        card=directory/'writing-card.json'
        if not card.exists():
            metadata=json.loads((source/'card.json').read_text())
            card.write_text(json.dumps({**metadata,'skill_path':str(target/'SKILL.md')},ensure_ascii=False,indent=2))
            card.chmod(0o600)
        print('作者规则可用（不包含原始语料）')
    if values: core.save_settings(values);print('本地配置已保存；凭据未输出')
    if args.check:
        cfg=core.settings()
        print(json.dumps({'text_model':cfg['text_model'],'vision_model':cfg['vision_model'],
            'whisper_model_ready':(Path(cfg['whisper_model'])/'model.bin').is_file(),
            'authors':[a['name'] for a in author_profiles.catalog()],
            'dify':{m:{'app_id':k.get('app_id'),'key_configured':bool(k.get('api_key'))} for m,k in cfg['dify_keys'].items()}},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
