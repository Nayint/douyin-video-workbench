from . import creation_references
import asyncio
import json
import os
import re
import shutil
import sqlite3
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from PIL import Image
from . import core, jobs, media, dify, dify_models, note_layout, models, spoken, products as product_tools
from . import author_profiles, writing_guard, writing_learning

@asynccontextmanager
async def lifespan(app):
    core.init_db()
    core.repair_note_uris()
    cfg=core.settings()
    for folder in note_layout.FOLDERS:
        core.contained(cfg['vault_path'],cfg['vault_subdir']+'/'+folder).mkdir(parents=True,exist_ok=True)
    jobs.start()
    yield
    jobs.STOP.set(); jobs.WAKE.set()

app=FastAPI(title='ViralLab',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',redoc_url=None)
# The private estate extension is optional in the public workbench.
from importlib.util import find_spec
if find_spec('backend.world_chat') is not None:
    from . import world_chat
    app.include_router(world_chat.router)

@app.middleware('http')
async def local_boundary(request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('127.0.0.1','localhost','[::1]'):
        return JSONResponse({'detail':'仅允许本机访问'},status_code=403)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin not in (f'http://{request.headers.get("host")}',):
            return JSONResponse({'detail':'拒绝跨站写入请求'},status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'拒绝跨站请求'},status_code=403)
    length=request.headers.get('content-length')
    if length and not length.isdigit():return JSONResponse({'detail':'无效请求大小'},status_code=400)
    if length and int(length)> (core.settings()['max_upload_mb']+2)*1024*1024:
        return JSONResponse({'detail':'上传内容超过本机大小限制'},status_code=413)
    total=0
    receive=request._receive
    async def bounded_receive():
        nonlocal total
        message=await receive()
        total+=len(message.get('body',b''))
        if total>(core.settings()['max_upload_mb']+2)*1024*1024:raise HTTPException(413,'上传内容超过本机大小限制')
        return message
    request._receive=bounded_receive
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
    # Only the isolated physics worker may compile WebAssembly. Document CSP is unchanged.
    if request.url.path.startswith('/assets/worldPhysicsWorker-') and request.url.path.endswith('.js'):
        response.headers['Content-Security-Policy']="default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'"
    return response

@app.exception_handler(PermissionError)
async def permission_error(request,e):return JSONResponse({'detail':'Obsidian 或本地存储目录没有权限，请检查系统设置'},status_code=400)

@app.exception_handler(ValueError)
async def invalid(request,e):return JSONResponse({'detail':str(e)},status_code=400)

class CaseInput(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    platform:str=Field(default='本地',max_length=30)
    source_url:str=Field(default='',max_length=4096)
    author:str=Field(default='',max_length=200)
    account:str=Field(default='',max_length=200)
    published_at:str|None=None
    transcript:str=Field(default='',max_length=150000)
    notes:str=Field(default='',max_length=30000)
    category:str=Field(default='',max_length=100)
    tags:list[str]=Field(default_factory=list,max_length=30)
    favorite:bool=False
    metrics:dict=Field(default_factory=dict)
    publication_title:str=Field(default='',max_length=1000)
    publication_caption:str=Field(default='',max_length=30000)
    publication_hashtags:list[str]=Field(default_factory=list,max_length=100)
    collect_only:bool=False
    auto_analyze:bool=False

class CasePatch(BaseModel):
    cover_product_id:str|None=None
    cover_reference_style:str|None=Field(default=None,max_length=5000)
    cover_reference_case_id:str|None=None
    publication_title:str|None=Field(default=None,max_length=1000)
    publication_caption:str|None=Field(default=None,max_length=30000)
    publication_hashtags:list[str]|None=Field(default=None,max_length=100)
    title:str|None=Field(default=None,min_length=1,max_length=200)
    author:str|None=Field(default=None,max_length=200)
    account:str|None=Field(default=None,max_length=200)
    platform:str|None=Field(default=None,max_length=30)
    published_at:str|None=Field(default=None,max_length=100)
    transcript:str|None=Field(default=None,max_length=150000)
    notes:str|None=Field(default=None,max_length=30000)
    tags:list[str]|None=None
    category:str|None=Field(default=None,max_length=100)
    favorite:bool|None=None
    metrics:dict|None=None
    cover:str|None=None

class JobInput(BaseModel):
    type:str
    request_key:str
    material:dict=Field(default_factory=dict)

class DraftInput(BaseModel):
    content:str=Field(min_length=1,max_length=150000)

async def save_upload(file,case_id,allowed,limit=None):
    ext=Path(file.filename or '').suffix.lower()
    if ext not in allowed:raise ValueError('不支持的文件类型：'+ext)
    directory=core.media_root()/case_id; directory.mkdir(parents=True,exist_ok=True)
    path=directory/(core.uid()+ext); size=0
    try:
        with path.open('xb') as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>(limit or core.settings()['max_upload_mb'])*1024*1024:raise ValueError('文件超过允许大小')
                out.write(chunk)
        if size==0:raise ValueError('上传文件为空')
        return path
    except Exception:
        path.unlink(missing_ok=True);raise
    finally:await file.close()

@app.get('/api/health')
def health():return {'name':'ViralLab','version':'1.0.0','status':'ok'}

@app.get('/api/dashboard')
def dashboard():
    cases=core.records('case'); analyses=[a for a in core.records('analysis') if not a.get('case_id') or a['case_id'] in {c['id'] for c in cases}]
    researched={x['case_id'] for x in analyses if x.get('case_id')}
    visible_drafts=[d for d in core.records('draft') if not d.get('deleted_at')]
    return {'total':sum(c['id'] not in researched for c in cases),'total_all':len(cases),'analyzed':len(researched),
        'pending':sum(t['status'] in ('queued','running','failed','interrupted') for t in tasks()),
        'recent':[c for c in cases if c['id'] not in researched][:6],'favorites':[x for x in cases if x.get('favorite')][:6],
        'drafts_total':len(visible_drafts),'drafts':visible_drafts[:5],'reports':analyses[:5]}

@app.get('/api/cases')
def cases(q:str='',favorite:bool=False,category:str='',tag:str='',sort:str='updated_at'):
    researched={a.get('case_id') for a in core.records('analysis')}
    rows=[{**c,'has_research':c['id'] in researched} for c in core.records('case')]
    rows=[r for r in rows if (not q or q.lower() in core.dumps(r).lower()) and (not favorite or r.get('favorite')) and (not category or category==r.get('category')) and (not tag or tag in r.get('tags',[]))]
    if sort=='title':rows.sort(key=lambda r:r['title'])
    elif sort=='duration':rows.sort(key=lambda r:r.get('duration',0),reverse=True)
    return rows

def validate_metrics(metrics):
    from datetime import datetime
    for key in ('likes','comments','favorites','shares'):
        v=metrics.get(key)
        if v is not None and (isinstance(v,bool) or not isinstance(v,int) or v<0):
            raise ValueError('公开指标应为非负整数，未知填写 null')
    if any(metrics.get(k) is not None for k in ('likes','comments','favorites','shares')):
        if not metrics.get('source') or not metrics.get('collected_at'):
            raise ValueError('填写公开指标时必须同时记录 source 来源与 collected_at 采集时间')
        try:datetime.fromisoformat(metrics['collected_at'])
        except (ValueError,TypeError):raise ValueError('指标采集时间必须为 ISO 日期时间')
    return metrics

@app.post('/api/cases')
def create_case(data:CaseInput):
    values=data.model_dump();values.pop('collect_only',None);values.pop('auto_analyze',None);text=values.pop('transcript');values['metrics']={'likes':None,'comments':None,'favorites':None,'shares':None,'source':None,'collected_at':core.now(),**values['metrics']}
    if values['source_url'] and urlparse(values['source_url']).scheme not in ('http','https'):raise ValueError('原始链接只允许 HTTP/HTTPS')
    validate_metrics(values['metrics'])
    case=core.put('case',values)
    if text:jobs.save_transcript(case,text)
    jobs.case_note(core.get(case['id']))
    return core.get(case['id'])

@app.get('/api/cases/{id}')
def case_detail(id):
    case=core.get(id,'case')
    return {**case,'transcript':jobs.transcript(case),'analyses':[a for a in core.records('analysis') if a.get('case_id')==id]}

@app.patch('/api/cases/{id}')
def edit_case(id,data:CasePatch):
    case=core.get(id,'case');values=data.model_dump(exclude_none=True)
    if 'cover' in values and values['cover'] not in [f['path'] for f in case.get('frames',[])]: raise ValueError('只能选择此案例的关键帧')
    if 'metrics' in values:validate_metrics(values['metrics'])
    if any(k in values for k in ('publication_title','publication_caption','publication_hashtags')):
        values['publication_source']='人工补充或校对'
        values['publication_collected_at']=core.now()
    text=values.pop('transcript',None)
    if text is not None:
        result=jobs.save_transcript(case,text)
        if result['conflict']:return JSONResponse(result,status_code=409)
    core.update_record(id,values);sync=jobs.case_note(core.get(id))
    return {**case_detail(id),'sync':sync}

@app.post('/api/cases/upload')
async def upload_video(file:UploadFile,title:str=Form(''),collect_only:bool=Form(False),auto_analyze:bool=Form(False)):
    id=core.uid();path=await save_upload(file,id,media.VIDEO_EXT)
    try:info=await asyncio.to_thread(media.probe,path)
    except Exception:
        path.unlink(missing_ok=True);raise
    case=core.put('case',{'title':title.strip() or Path(file.filename).stem,'platform':'本地','video':str(path.relative_to(core.media_root())),
        **info,'tags':[],'metrics':{'likes':None,'comments':None,'favorites':None,'shares':None,'source':None,'collected_at':core.now()}},id)
    jobs.case_note(case)
    task=None if collect_only else jobs.enqueue('research_all' if auto_analyze else 'process',id,{},'import-'+id)
    return {'case':case,'task':task}

@app.post('/api/cases/link')
def import_link(data:CaseInput):
    normalized=media.extract_douyin_url(data.source_url)
    case=create_case(data.model_copy(update={'source_url':normalized}))
    return {'case':case,'task':None if data.collect_only else jobs.enqueue('research_all' if data.auto_analyze else 'link',case['id'],{},'link-'+case['id'])}

@app.post('/api/cases/{id}/metadata')
def refresh_metadata(id,data:JobInput):
    case=core.get(id,'case')
    if not case.get('source_url'):raise ValueError('本地视频没有原始链接，仅能提取文件内的信息')
    active=next((t for t in tasks() if t['resource_id']==id and t['kind']=='metadata' and t['status'] in ('queued','running')),None)
    return active or jobs.enqueue('metadata',id,{},data.request_key)

@app.post('/api/cases/{id}/research')
def research_all(id,data:JobInput):
    core.get(id,'case')
    active=next((t for t in tasks() if t['resource_id']==id and t['kind']=='research_all' and t['status'] in ('queued','running')),None)
    return active or jobs.enqueue('research_all',id,{},data.request_key)

@app.delete('/api/cases/{id}')
def delete_case(id):
    core.get(id,'case')
    with core.db() as c:
        active=c.execute("SELECT id FROM tasks WHERE resource_id=? AND status IN ('queued','running')",(id,)).fetchone()
        if active:raise ValueError('此素材正在处理，请等待任务结束后删除')
        # Remove from the workbench only; preserve source files, drafts and human notes.
        c.execute("UPDATE records SET kind='archived_case' WHERE id=? AND kind='case'",(id,))
    note_layout.migrate();note_layout.refresh_indexes()
    return {'deleted':id,'notice':'已从工作台移除，原始文件、Obsidian 笔记及历史文案保留'}

@app.post('/api/cases/{id}/restore')
def restore_case(id):
    core.get(id,'archived_case')
    with core.db() as c:c.execute("UPDATE records SET kind='case' WHERE id=?",(id,))
    note_layout.migrate();note_layout.refresh_indexes()
    return core.get(id,'case')

@app.post('/api/cases/{id}/process')
def process(id,data:JobInput):
    case=core.get(id,'case')
    if not case.get('video'):raise ValueError('此案例没有本地视频，请使用上传入口')
    return jobs.enqueue('process',id,{},data.request_key)

@app.post('/api/cases/{id}/video')
async def attach_video(id,file:UploadFile):
    case=core.get(id,'case')
    if case.get('video'):raise ValueError('此案例已有本地视频，不覆盖原始素材；可重新处理已有视频')
    path=await save_upload(file,id,media.VIDEO_EXT)
    try:info=await asyncio.to_thread(media.probe,path)
    except Exception:
        path.unlink(missing_ok=True);raise
    case=core.update_record(id,{'video':str(path.relative_to(core.media_root())),**info})
    return {'case':case,'task':jobs.enqueue('process',id,{},'attach-'+id)}

@app.post('/api/cases/{id}/cover')
async def cover(id,file:UploadFile):
    core.get(id,'case');path=await save_upload(file,id,media.IMAGE_EXT,20)
    try:path=await asyncio.to_thread(media.normalize_image,path)
    except Exception:raise ValueError('封面不是有效图片或图片过大')
    core.update_record(id,{'cover':str(path.relative_to(core.media_root())),'cover_provenance':{'source':'人工上传的封面','collected_at':core.now()}})
    return case_detail(id)

@app.post('/api/cases/{id}/fetch-cover')
def fetch_cover(id,data:JobInput):
    core.get(id,'case')
    return jobs.enqueue('fetch_cover',id,{},data.request_key)

@app.post('/api/cases/{id}/analyze')
def analyze_case(id,data:JobInput):
    core.get(id,'case')
    if data.type=='cover':
        product_id=data.material.get('product_id')
        if product_id:core.get(product_id,'product')
        reference_id=data.material.get('reference_case_id')
        if reference_id:core.get(reference_id,'case')
        core.update_record(id,{'cover_product_id':product_id,'cover_draft_id':data.material.get('draft_id'),'cover_reference_style':str(data.material.get('reference_style',''))[:5000],'cover_reference_case_id':reference_id})
    if data.type not in ('video','title','cover','cover_visual'):raise ValueError('无效分析类型')
    return jobs.enqueue('analysis',id,{'type':data.type},data.request_key)

@app.post('/api/research')
def research(data:JobInput):
    if data.type not in ('title','compare','suggest'):raise ValueError('无效研究类型')
    if len(core.dumps(data.material))>150000:raise ValueError('研究资料过长')
    return jobs.enqueue('analysis',None,{'type':data.type,'material':data.material},data.request_key)

@app.get('/api/analyses')
def analyses():return core.records('analysis')

@app.post('/api/analyses/{id}/versions')
def edit_analysis(id,data:dict):
    old=core.get(id,'analysis')
    if not isinstance(data.get('result'),dict) or len(core.dumps(data))>150000:raise ValueError('分析必须为 JSON 对象')
    new=core.put('analysis',{**old,'result':data['result'],'human':True,'parent_id':id,'note':None})
    folder,note_title=note_layout.analysis_location(new)
    sync=core.sync_note(folder,new['id'],note_title+' · 人工修订','```json\n'+json.dumps(data['result'],ensure_ascii=False,indent=2)+'\n```',{'parent_id':id,'human':True})
    core.update_record(new['id'],{'note':sync})
    if old.get('case_id'):jobs.case_note(core.get(old['case_id']))
    return core.get(new['id'])

@app.get('/api/titles')
def titles():return core.records('title')

@app.post('/api/titles')
def save_title(data:dict):
    title=str(data.get('title','')).strip()
    if not title or len(title)>200:raise ValueError('标题需为 1–200 字')
    return core.put('title',{'title':title,'category':str(data.get('category',''))[:100],'structure':str(data.get('structure',''))[:100],'case_id':data.get('case_id')})

@app.get('/api/products')
def products():
    return [{**p,'content':core.note_read(p['note']['path'])} for p in core.records('product')]

@app.delete('/api/products/{id}')
def delete_product(id):
    with core.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT kind FROM records WHERE id=?',(id,)).fetchone()
        if not row or row['kind'] not in ('product','archived_product'):raise ValueError('产品不存在')
        active=c.execute("SELECT resource_id,payload FROM tasks WHERE status IN ('queued','running')").fetchall()
        if any(t['resource_id']==id or json.loads(t['payload']).get('product_id')==id for t in active):
            raise ValueError('此产品正在分析或用于文案创作，请等待任务结束后删除')
        c.execute("UPDATE records SET kind='archived_product' WHERE id=?",(id,))
    return {'deleted':id,'notice':'已从产品库移除，原始资料、分析版本和已有文案保留，可撤销删除'}

@app.post('/api/products/{id}/restore')
def restore_product(id):
    with core.db() as c:
        row=c.execute('SELECT kind FROM records WHERE id=?',(id,)).fetchone()
        if not row or row['kind'] not in ('product','archived_product'):raise ValueError('产品不存在')
        c.execute("UPDATE records SET kind='product' WHERE id=?",(id,))
    return core.get(id,'product')

@app.post('/api/products')
def product(data:dict):
    name=str(data.get('name','')).strip();content=str(data.get('content','')).strip()
    if not name or not content or len(content)>100000:raise ValueError('请填写产品名称及真实产品资料（最多10万字）')
    id=core.uid();sync=core.sync_note('产品资料',id,name,content,{'type':'product'})
    p=core.put('product',{'name':name,'note':sync,'files':[]},id)
    note_layout.refresh_indexes()
    return p

@app.post('/api/products/{id}/analyze')
def analyze_product(id,data:dict):
    core.get(id,'product')
    instruction=str(data.get('instruction','')).strip()
    if len(instruction)>10000:raise ValueError('更新要求最多1万字')
    return jobs.enqueue('product_analysis',id,{'instruction':instruction},data.get('request_key'))

@app.get('/api/products/{id}/versions')
def product_versions(id):
    core.get(id,'product')
    return [v for v in core.records('product_version') if v['product_id']==id]

@app.post('/api/products/{id}/files')
async def product_file(id,file:UploadFile):
    p=core.get(id,'product')
    if len(p.get('files',[]))>=5:raise ValueError('每份产品资料最多 5 个文件')
    path=await save_upload(file,id,media.DOC_EXT|media.IMAGE_EXT,15)
    if path.suffix in media.IMAGE_EXT:
        try:path=media.normalize_image(path)
        except Exception:raise ValueError('产品图片无效')
    return core.update_record(id,{'analysis_status':'pending','files':p.get('files',[])+[{'name':file.filename,'path':str(path.relative_to(core.media_root())),'type':'image' if path.suffix in media.IMAGE_EXT else 'document'}]})

@app.post('/api/products/import')
def import_products():
    cfg=core.settings();root=core.contained(cfg['vault_path'],cfg['product_subdir'])
    if not root.exists():raise ValueError('产品资料目录不存在，请先在授权目录放入 Markdown 文件')
    existing={p['note']['path'] for p in core.records('product')+core.records('archived_product')};count=0
    for path in root.rglob('*.md'):
        if path.is_symlink() or not path.resolve().is_relative_to(root) or '.conflict-' in path.name or '--index-' in path.name:continue
        relative=str(path.relative_to(cfg['vault_path']))
        if relative not in existing:
            if path.stat().st_size>300000:continue
            core.put('product',{'name':path.stem,'note':{'path':relative,'status':'external'},'files':[]});count+=1
    return {'imported':count}

@app.get('/api/tasks')
def tasks():
    with core.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM tasks WHERE dismissed_at IS NULL ORDER BY created_at DESC LIMIT 100')]
    archived={c['id'] for c in core.records('archived_case')}
    rows=[jobs.task_get(id) for id in ids]
    return [t for t in rows if t['resource_id'] not in archived]

@app.get('/api/tasks/{id}')
def task(id):return jobs.task_get(id)

@app.delete('/api/tasks/{id}')
def dismiss_task(id):
    # Keep execution state, remote run IDs and idempotency records intact.
    jobs.task_get(id)
    jobs.task_update(id,dismissed_at=core.now())
    return {'id':id,'dismissed':True}

@app.post('/api/tasks/{id}/restore')
def restore_task(id):
    jobs.task_get(id)
    jobs.task_update(id,dismissed_at=None)
    return jobs.task_get(id)

@app.post('/api/tasks/{id}/resume')
def resume(id):
    t=jobs.task_get(id)
    if t['kind']=='dify':
        if not t.get('run_id'):raise ValueError('未收到运行编号，无法判断远端是否已执行；请先检查 Dify 历史，不能自动重发')
        d=dify.request(t['payload']['mode'],'GET','workflows/run/'+t['run_id'])
        if d['status']=='succeeded':
            content=d.get('outputs',{}).get('final_copy')
            if not content:raise ValueError('Dify 完成但没有文案输出')
            if t['payload'].get('model_runtime'):
                try:actual=dify_models.executed(t['payload']['mode'],t['run_id'])
                except (ValueError,KeyError):actual=[]
                jobs.task_update(id,payload=core.dumps({**t['payload'],'actual_models':actual}))
            draft=jobs.finish_copy(jobs.task_get(id),content)
            jobs.task_update(id,status='succeeded',stage='已恢复远端结果',progress=1,error=None,result=core.dumps({'draft_id':draft['id'],'note':draft['note'],'fact_check':draft.get('fact_check')}))
        else:jobs.task_update(id,stage='Dify 远端状态：'+d['status'])
    else:
        if t['status'] not in ('failed','interrupted'):raise ValueError('只能重试失败或中断任务')
        jobs.task_update(id,status='queued',stage='等待重试',error=None);jobs.WAKE.set()
    return jobs.task_get(id)

@app.get('/api/dify/parameters/{mode}')
def dify_params(mode):return dify.parameters(mode)

@app.get('/api/authors')
def authors():return author_profiles.catalog()

class GenerateInput(BaseModel):
    case_id:str=''
    product_id:str
    mode:str='prototype'
    request_key:str
    extra_requirements:str=Field(default='',max_length=5000)
    draft_name:str=Field(default='',max_length=200)
    expected_models:dict[str,str]|None=None
    author_id:str=Field(default='',max_length=200)
    writing_mode:str=Field(default='生活分享',max_length=30)
    personal_experience:str=Field(default='',max_length=3000)
    expected_input_hash:str|None=None
    learning_ids:list[str]|None=None

@app.get('/api/creation/references')
def creation_reference_catalog():
    return creation_references.catalog()

def prepare_creation(data:GenerateInput):
    p=core.get(data.product_id,'product')
    profile=author_profiles.load(data.author_id) if data.author_id else None
    c=creation_references.require(data.case_id) if data.case_id else None
    if not profile and not c:raise ValueError('请选择作者风格或参考案例')
    if data.writing_mode not in author_profiles.MODES:raise ValueError('未知的作者写作方式')
    if profile and data.mode!='prototype':raise ValueError('作者写作不使用链接工作流')
    structure=creation_references.structure(c['id'],core.settings()['text_model']) if profile and c else None
    learning=writing_learning.choose(data.author_id or 'default',data.writing_mode,p.get('category',''),data.learning_ids)
    material=product_tools.dify_material(p)
    requirements=data.extra_requirements.rstrip()+'\n\n'+spoken.FORMAT_REQUIREMENT
    requirements+='\n\n【称呼习惯】默认使用朋友、朋友们等中性称呼，也可以直接进入内容；除非本次明确指定，不惯用姐妹、姐妹们或家人们。参考视频中的称呼不随架构迁移。'
    if data.personal_experience:requirements+='\n\n【用户明确提供的真实体验】\n'+data.personal_experience
    base_requirements=requirements
    if not profile:
        while learning and len(base_requirements+writing_learning.instruction(learning))>5000 and data.learning_ids is None:
            learning.pop()
    requirements=base_requirements+writing_learning.instruction(learning)
    if not profile and len(requirements)>5000:
        raise ValueError('本次要求、真实体验与沉淀合计超过Dify的5000字限制，请精简要求或减少勾选经验')
    grounding=writing_guard.snapshot(p['name'],material,data.personal_experience,
        author_hash=profile['skill_hash'] if profile else '',writing_mode=data.writing_mode,
        requirements=data.extra_requirements,product_id=p['id'],case_id=data.case_id,mode=data.mode,
        structure_hash=structure['hash'] if structure else '',learning_hash=writing_guard.digest(learning))
    inputs={'source_material':material,'product_files':[],'extra_requirements':requirements.strip()}
    selection={k:core.settings()[k] for k in ('text_model','vision_model')}
    if profile:
        return {'mode':'author','inputs':inputs,'grounding':grounding,
                'author':author_profiles.public(profile),'_author':profile,'structure_reference':structure,'learning_entries':learning,
                'model_selection':selection,'notice':'按作者写作卡生成，逐句核对本次资料，通过后保存到原创文案。'}
    if data.mode=='prototype':inputs.update(prototype_file={'pending_upload':'案例逐字稿 Markdown'},content_type='口播文案',style_mode='干净口语版',platform_purpose='抖音原创口播')
    elif data.mode=='link':
        if not c.get('source_url'):raise ValueError('此案例没有视频链接，请选择原型 Markdown 工作流')
        inputs.update(video_url=c['source_url'],video_name=c['title'],product_name=p['name'],cache_mode='自动复用（失败续跑）')
    else:raise ValueError('未知工作流')
    dify.validate_inputs(data.mode,inputs)
    return {'mode':data.mode,'inputs':inputs,'grounding':grounding,'author':None,'learning_entries':learning,'model_selection':selection,'notice':'生成后逐句核对本次产品资料，通过后保存到原创文案。'}

@app.post('/api/dify/preview')
def preview(data:GenerateInput):
    return {k:v for k,v in prepare_creation(data).items() if not k.startswith('_')}

@app.post('/api/dify/generate')
def generate(data:GenerateInput):
    p=prepare_creation(data)
    if data.expected_models is not None and data.expected_models!=p['model_selection']:
        raise ValueError('模型设置在预览后发生变化，请重新核对创作资料再生成')
    if data.expected_input_hash and data.expected_input_hash!=p['grounding']['hash']:
        raise ValueError('产品资料、真实体验、作者卡或参考架构在预览后发生变化，请重新核对创作资料')
    payload={'mode':data.mode,'product_id':data.product_id,'inputs':p['inputs'],
             'draft_name':data.draft_name.strip(),'model_selection':p['model_selection'],
             'grounding':p['grounding'],'author':p.get('_author'),
             'writing_mode':data.writing_mode,'case_id':data.case_id or None,
             'structure_reference':p.get('structure_reference'),'learning_entries':p.get('learning_entries',[])}
    return jobs.enqueue('author_write' if data.author_id else 'dify',data.case_id or data.product_id,payload,data.request_key)

@app.get('/api/drafts')
def drafts():return [{**d,'title':note_layout.draft_title(d),'content':spoken.layout_document(core.note_read(d['note']['path']))} for d in sorted(core.records('draft'),key=lambda d:d['created_at'],reverse=True) if not d.get('deleted_at')]

@app.delete('/api/drafts/{id}')
def delete_draft(id):
    d=core.get(id,'draft')
    # Retain task deduplication, version links, filming state and the original note.
    if not d.get('deleted_at'):core.update_record(id,{'deleted_at':core.now()})
    return {'deleted':id,'notice':'已从原创文案移除，原稿和关联资料保留，可撤销删除'}

@app.post('/api/drafts/{id}/restore')
def restore_draft(id):
    core.get(id,'draft')
    return core.update_record(id,{'deleted_at':None})

class DraftFilmingInput(BaseModel):
    filmed: bool

@app.patch('/api/drafts/{id}/filming')
def set_draft_filming(id, data:DraftFilmingInput):
    core.get(id, 'draft')
    return core.update_record(id, {'filmed': data.filmed, 'filmed_at': core.now() if data.filmed else None})

@app.post('/api/drafts/{id}/versions')
def revise_draft(id,data:DraftInput):
    d=core.get(id,'draft')
    new=jobs.draft_version(d['case_id'],d['product_id'],data.content,parent_id=id)
    writing_learning.capture_revision(d,new)
    jobs.WAKE.set()
    return new

class FeedbackInput(BaseModel):
    id:str|None=None
    body_hash:str=Field(max_length=64)
    start:int=Field(ge=0)
    end:int=Field(ge=1)
    quote:str=Field(max_length=30000)
    rating:str
    scope:str='global'
    reason:str=Field(default='',max_length=3000)
    replacement:str=Field(default='',max_length=10000)

@app.get('/api/drafts/{id}/feedback')
def feedback_list(id):
    d=core.get(id,'draft');text=writing_learning.body(d)
    return {'body':text,'body_hash':writing_learning.digest(text),
            'entries':[r for r in writing_learning.feedback_rows() if r['draft_id']==id]}

@app.post('/api/drafts/{id}/feedback')
def feedback_save(id,data:FeedbackInput):
    row=writing_learning.save(id,data.model_dump());jobs.WAKE.set()
    return row

@app.delete('/api/learning/{id}')
def feedback_revoke(id):
    row=writing_learning.revoke(id);jobs.WAKE.set();return row

@app.post('/api/learning/{id}/retry')
def feedback_retry(id):
    row=core.get(id,'writing_feedback')
    updated=core.update_record(id,{'revision':row['revision']+1,'sync_status':'pending','sync_error':None})
    jobs.WAKE.set();return updated

@app.get('/api/learning')
def learning_list():return writing_learning.feedback_rows()

@app.get('/api/drafts/{id}/export')
def export(id,format:str='md'):
    d=core.get(id,'draft');content=spoken.layout_document(core.note_read(d['note']['path']))
    if format=='txt':content=spoken.plain_lines(spoken.plain_body(content))
    return Response(content,media_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="virallab-{id}.{ "txt" if format=="txt" else "md" }"'})

@app.post('/api/cases/{id}/sync')
def sync(id):return jobs.case_note(core.get(id,'case'))

@app.get('/api/note')
def note(path:str):
    cfg=core.settings();allowed=core.contained(cfg['vault_path'],cfg['vault_subdir'])
    target=core.contained(cfg['vault_path'],path)
    if not target.is_relative_to(allowed):raise ValueError('笔记不在授权的 ViralLab 子目录')
    return {'content':target.read_text()}

@app.get('/api/settings')
def get_settings():
    cfg=core.settings();keys=cfg.pop('dify_keys')
    return {**cfg,'dify_model_status':dify_models.status(),'dify_workflows':{k:{'configured':bool(v.get('api_key')),'app_id':v.get('app_id')} for k,v in keys.items()}}

@app.put('/api/settings')
def set_settings(data:dict):
    allowed=set(core.DEFAULTS)-{'dify_keys'}
    values={k:v for k,v in data.items() if k in allowed}
    for key in ('ollama_url','dify_url','bilinote_url'):
        if key in values:values[key]=core.local_url(str(values[key]))
    if 'cover_style_profile' in values:
        if not isinstance(values['cover_style_profile'],str) or not 20<=len(values['cover_style_profile'])<=10000:raise ValueError('系列封面风格请填写20至10000字的固定规范')
    cfg=core.settings()
    for path_key in ('vault_path','vault_subdir','storage_path'):
        if path_key in values and values[path_key]!=cfg[path_key] and core.records('case'):
            raise ValueError('已有案例时不能直接切换存储路径，请先备份并按迁移说明处理')
    for key in ('vault_subdir','product_subdir'):
        if key in values:core.contained(values.get('vault_path',cfg['vault_path']),values[key])
    if 'vault_path' in values and not Path(values['vault_path']).is_dir():raise ValueError('Obsidian Vault 目录不存在')
    if 'product_subdir' in values:
        product_path=core.contained(values.get('vault_path',cfg['vault_path']),values['product_subdir'])
        allowed_path=core.contained(values.get('vault_path',cfg['vault_path']),values.get('vault_subdir',cfg['vault_subdir']))
        if not product_path.is_relative_to(allowed_path):raise ValueError('产品目录必须位于授权的 ViralLab 子目录')
    for key,lo,hi in [('max_upload_mb',1,2000),('frame_count',1,30),('model_timeout',30,1800)]:
        if key in values:values[key]=int(values[key])
        if key in values and not lo<=values[key]<=hi:raise ValueError('设置数值超出范围')
    models.validate(values,cfg)
    keys=cfg['dify_keys']
    for mode in ('prototype','link'):
        key=data.get(mode+'_api_key')
        if key:keys[mode]={**keys.get(mode,{}),'api_key':str(key).strip()}
    values['dify_keys']=keys
    combined={**cfg,**values}
    synced=dify_models.status()
    if (any(values.get(k,cfg[k])!=cfg[k] for k in ('text_model','vision_model','ollama_url')) or
        any(key.get('api_key') and any(synced.get(mode,{}).get(k)!=combined[k] for k in ('text_model','vision_model')) for mode,key in keys.items())):
        for mode,key in keys.items():
            if key.get('api_key'):
                dify_models.prepare(mode,combined,combined)
    core.save_settings(values);return get_settings()

@app.post('/api/models')
def local_models(data:dict):
    return {'models':models.inventory(data.get('ollama_url'))}

@app.get('/api/connections')
def connections():
    cfg=core.settings();result={}
    for name,url in [('ollama',core.local_url(cfg['ollama_url'])+'/api/tags')]:
        try:
            with httpx.Client(trust_env=False,timeout=8) as c:
                r=c.get(url);r.raise_for_status();result[name]={'ok':True,**r.json()}
        except httpx.HTTPError:result[name]={'ok':False,'error':'Ollama 未运行或连接失败'}
    try:
        r=httpx.get(core.local_url(cfg['bilinote_url'])+'/api/task_history',timeout=8,trust_env=False)
        r.raise_for_status()
        result['bilinote']={'ok':r.json().get('code')==0}
    except (httpx.HTTPError,ValueError):
        result['bilinote']={'ok':False,'error':'原 Dify 使用的 BiliNote 服务连接失败'}
    for mode in ('prototype','link'):
        try:result['dify_'+mode]={'ok':True,'fields':list(dify.form_fields(dify.parameters(mode)))}
        except ValueError as e:result['dify_'+mode]={'ok':False,'error':str(e)}
    result['obsidian']={'ok':Path(cfg['vault_path']).is_dir() and os.access(cfg['vault_path'],os.W_OK),'path':cfg['vault_path']}
    result['whisper']={'ok':(Path(cfg['whisper_model'])/'model.bin').is_file(),'path':cfg['whisper_model']}
    return result

@app.post('/api/backups')
def backup():
    from .backup import create_backup
    path=create_backup();return {'filename':path.name,'url':'/api/backups/'+path.name,'notice':'备份含本机凭据，请妥善保管；恢复前停止 ViralLab'}

@app.get('/api/backups/{filename}')
def download_backup(filename):
    if not re.fullmatch(r'virallab-[0-9a-f-]+\.zip',filename):raise ValueError('无效备份名')
    path=core.contained(core.ROOT/'backups',filename)
    if not path.is_file():raise ValueError('备份不存在')
    return FileResponse(path,filename=filename)

@app.get('/media/{path:path}')
def media_file(path):
    file=core.contained(core.media_root(),path)
    if not file.is_file():raise ValueError('媒体文件不存在')
    return FileResponse(file)

DIST=core.ROOT/'frontend/dist'
@app.get('/{path:path}')
def frontend(path):
    if path.startswith('api/'):raise HTTPException(404,'接口不存在')
    if DIST.exists():
        p=(DIST/path).resolve()
        if p.is_relative_to(DIST) and p.is_file():return FileResponse(p)
        return FileResponse(DIST/'index.html')
    return JSONResponse({'message':'前端尚未构建，请执行 npm run build'},status_code=503)
