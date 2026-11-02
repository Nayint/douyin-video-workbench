"""Read-only checks of installed models and Dify public contracts; never print keys."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import core,dify,dify_models,author_profiles
import httpx


def main():
    cfg=core.settings();reference=json.loads((core.ROOT/'config/reference-environment.json').read_text())
    failed=False
    try:
        with httpx.Client(trust_env=False,timeout=20) as client:
            response=client.get(core.local_url(cfg['ollama_url'])+'/api/tags');response.raise_for_status()
            installed={m['name']:m for m in response.json()['models']}
            for name in (cfg['text_model'],cfg['vision_model']):
                found=installed.get(name)
                expected=next((m for m in reference['models'] if m['name']==name),None)
                equal=found and expected and found['digest']==expected['digest']
                print(('OK' if found else 'MISSING')+': model '+name+(' (reference digest matches)' if equal else ' (digest differs or not in reference)'))
                failed|=not bool(found)
    except (httpx.HTTPError,KeyError,ValueError): print('MISSING: Ollama connection/model inventory');failed=True
    authors=author_profiles.catalog();print('Authors: '+', '.join(a['name'] for a in authors))
    for mode in ('prototype','link'):
        if not cfg['dify_keys'].get(mode,{}).get('api_key'):
            print('SKIP: '+mode+' Dify key not configured');continue
        try:
            fields=dify.form_fields(dify.parameters(mode))
            audit=dify_models.call({'action':'audit','app_id':cfg['dify_keys'][mode]['app_id']})
            print('OK: '+mode+' Dify contract ('+str(len(fields))+' inputs), Docker audit ('+str(len(audit['nodes']))+' LLM nodes)')
        except (ValueError,KeyError):print('MISSING: '+mode+' Dify contract/container audit');failed=True
    print('This checks connectivity and configuration, not generation quality.')
    return int(failed)

if __name__=='__main__':raise SystemExit(main())
