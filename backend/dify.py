"""Use published API contracts, never debugger APIs or guessed variable names."""
import json
from pathlib import Path
import httpx
from .core import settings, local_url


def client(mode):
    cfg=settings(); key=cfg['dify_keys'].get(mode,{}).get('api_key','')
    if not key: raise ValueError('Dify 尚未配置此工作流 API Key，请在设置中填写')
    return httpx.Client(base_url=local_url(cfg['dify_url'])+'/',headers={'Authorization':'Bearer '+key},trust_env=False,
        timeout=httpx.Timeout(1800,connect=10))

def request(mode,method,path,**kw):
    try:
        with client(mode) as c:
            r=c.request(method,path,**kw)
            if r.is_error:
                # Never include raw response/request headers in errors.
                try: message=str(r.json().get('message',''))[:300]
                except ValueError: message='请检查 Dify 服务与工作流发布状态'
                raise ValueError(f'Dify 返回 HTTP {r.status_code}：{message}')
            return r.json()
    except httpx.TimeoutException: raise ValueError('Dify 请求超时；先查询执行状态，避免重复生成')
    except httpx.HTTPError: raise ValueError('Dify 连接失败，请检查服务地址与 API Key')

def parameters(mode): return request(mode,'GET','parameters')

def form_fields(params):
    fields={}
    for item in params.get('user_input_form',[]):
        for type,field in item.items():
            if isinstance(field,dict) and field.get('variable'): fields[field['variable']]={'type':type,**field}
    return fields

def validate_inputs(mode,inputs):
    fields=form_fields(parameters(mode))
    unknown=set(inputs)-set(fields)
    if unknown: raise ValueError('Dify 已发布契约不含字段：'+','.join(sorted(unknown)))
    for name,field in fields.items():
        v=inputs.get(name,field.get('default'))
        if field.get('required') and (v is None or v=='' or v==[]): raise ValueError('Dify 缺少必填参数：'+name)
        if isinstance(v,(str,list)) and field.get('max_length') and len(v)>field['max_length']:
            raise ValueError('Dify 参数超过已发布长度限制：'+name)
        if field.get('options') and v not in (None,'') and v not in field['options']:
            raise ValueError('Dify 参数不是已发布的可选值：'+name)
    return fields

def upload(mode,path,kind='document'):
    import mimetypes
    with Path(path).open('rb') as f:
        d=request(mode,'POST','files/upload',data={'user':'virallab-local'},files={'file':(Path(path).name,f,mimetypes.guess_type(str(path))[0] or 'application/octet-stream')})
    return {'type':kind,'transfer_method':'local_file','upload_file_id':d['id']}

def run(mode,inputs,progress,remote_ids,workflow_id=None):
    validate_inputs(mode,inputs)
    try:
        with client(mode) as c:
            path='workflows/run'
            if workflow_id:
                from uuid import UUID
                path='workflows/'+str(UUID(workflow_id))+'/run'
            with c.stream('POST',path,json={'inputs':inputs,'user':'virallab-local','response_mode':'streaming'}) as r:
                if r.is_error: raise ValueError(f'Dify 执行失败 HTTP {r.status_code}，请检查已发布工作流和参数')
                for line in r.iter_lines():
                    if not line.startswith('data:'): continue
                    try: event=json.loads(line[5:])
                    except ValueError: continue
                    data=event.get('data',{}); kind=event.get('event')
                    if event.get('workflow_run_id') or event.get('task_id'):
                        remote_ids(event.get('workflow_run_id'),event.get('task_id'))
                    if kind=='node_started': progress('Dify：'+str(data.get('title','正在执行节点')),.5)
                    if kind=='error': raise ValueError('Dify 工作流失败：'+str(event.get('message','未知原因'))[:300])
                    if kind=='workflow_finished':
                        if data.get('status')!='succeeded': raise ValueError('Dify 工作流未成功：'+str(data.get('error') or data.get('status'))[:300])
                        outputs=data.get('outputs',{})
                        if not isinstance(outputs.get('final_copy'),str) or not outputs['final_copy'].strip(): raise ValueError('Dify 未返回已确认的 final_copy 文案字段')
                        return outputs
        raise ValueError('Dify 连接已结束但未收到完成事件；请查询执行状态')
    except httpx.HTTPError: raise ValueError('Dify 执行连接中断或超时；先查询运行状态，不自动重新提交')
