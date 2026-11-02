"""Read installed Ollama capabilities; never pull or download models."""
import httpx
from . import core


def inventory(url=None):
    base=core.local_url(url or core.settings()['ollama_url'])
    try:
        with httpx.Client(trust_env=False,timeout=15) as client:
            response=client.get(base+'/api/tags');response.raise_for_status()
            result=[]
            for entry in response.json().get('models',[]):
                name=entry['name']
                try:
                    response=client.post(base+'/api/show',json={'model':name});response.raise_for_status()
                    caps=response.json().get('capabilities',[])
                    result.append({'name':name,'capabilities':caps,'text':'completion' in caps,'vision':'vision' in caps and 'completion' in caps})
                except (httpx.HTTPError,ValueError):
                    result.append({'name':name,'capabilities':[],'text':False,'vision':False,'error':'无法确认模型能力'})
            return result
    except (httpx.HTTPError,ValueError,KeyError):raise ValueError('无法读取本机 Ollama 模型，请检查服务地址和运行状态')


def validate(values,cfg):
    if not any(values.get(k,cfg[k])!=cfg[k] for k in ('text_model','vision_model','ollama_url')):return
    installed={m['name']:m for m in inventory(values.get('ollama_url',cfg['ollama_url']))}
    for key,cap,label in [('text_model','text','文字'),('vision_model','vision','视觉')]:
        name=values.get(key,cfg[key])
        if name not in installed:raise ValueError(f'{label}模型 {name} 未安装，设置未保存')
        if not installed[name][cap]:raise ValueError(f'模型 {name} 不支持{label}分析或能力无法确认，设置未保存')
