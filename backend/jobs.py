import sqlite3
from . import writing_learning
"""One persistent local worker; every analysis and draft revision is append-only."""
import json
import threading
import time
from pathlib import Path
from . import core, media, ai, dify, dify_models, bilinote, note_layout, cover_prompts, source_metadata, covers, products, spoken
from . import writing_guard, author_profiles

STOP=threading.Event()
WAKE=threading.Event()

def task_get(id):
    with core.db() as c: row=c.execute('SELECT * FROM tasks WHERE id=?',(id,)).fetchone()
    if not row: raise ValueError('任务不存在')
    result=dict(row)
    for key in ('payload','result'):
        if result[key]: result[key]=json.loads(result[key])
    return result

def task_update(id,**values):
    values['updated_at']=core.now()
    with core.db() as c:
        c.execute('UPDATE tasks SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),id))

def enqueue(kind,resource_id,payload,key):
    if not key or len(key)>150: raise ValueError('必须提供稳定请求编号')
    with core.db() as c:
        old=c.execute('SELECT id FROM tasks WHERE request_key=?',(key,)).fetchone()
        if old:
            existing=task_get(old[0])
            if existing['kind']!=kind or existing['resource_id']!=resource_id or existing['payload']!=payload:
                raise ValueError('同一请求编号的参数已变化，请另开一次创作；没有重复提交远端任务')
            return existing
        id=core.uid(); stamp=core.now()
        c.execute('INSERT INTO tasks(id,kind,resource_id,payload,status,stage,request_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (id,kind,resource_id,core.dumps(payload),'queued','等待处理',key,stamp,stamp))
    WAKE.set(); return task_get(id)

def case_note(case):
    note_layout.migrate()
    case=core.get(case['id'])
    analyses=[x for x in core.records('analysis') if x.get('case_id')==case['id']]
    transcript=case.get('transcript','')
    if case.get('transcript_note'):
        transcript=core.note_read(case['transcript_note'])
    body=f"# {case['title']}\n\n平台：{case.get('platform','本地')}\n\n原始链接：{case.get('source_url') or '未知'}\n\n## 原文转录\n\n{transcript or '尚未转写'}\n\n## 人工备注\n\n{case.get('notes','')}\n\n## 公开指标\n\n```json\n{core.dumps(case.get('metrics',{}))}\n```\n\n## 分析版本\n"
    body+='\n## 原视频发布信息\n\n标题：'+(case.get('publication_title') or '未知')+'\n\n发布文案：'+(case.get('publication_caption') or '未知')+'\n\n话题标签：'+(' '.join('#'+t for t in case.get('publication_hashtags',[])) or '未知')+'\n\n来源：'+(case.get('publication_source') or '未知')+'\n'
    for a in analyses:
        body+=f"\n### {note_layout.RESEARCH_NAMES.get(a['type'],a['type'])} · {a['created_at']}\n\n模型：{a['model']}；提示词：{a['prompt_version']}\n\n```json\n{json.dumps(a['result'],ensure_ascii=False,indent=2)}\n```\n"
    if case.get('cover'): body+='\n## 封面\n\n![]('+str(core.contained(core.media_root(),case['cover']))+')\n'
    sync=core.sync_note(note_layout.case_folder(case['id']),case['id'],case['title'],body,{'platform':case.get('platform'),'source_url':case.get('source_url')})
    core.update_record(case['id'],{'note':sync})
    note_layout.refresh_indexes()
    return sync

def save_transcript(case,text,segments=None):
    sync=core.sync_note(note_layout.case_folder(case['id']),case['id']+'-transcript',case['title']+' · 口播逐字稿',text,{'case_id':case['id'],'type':'transcript'})
    if sync['status']=='conflict': return {'note':sync,'conflict':True}
    changes={'transcript_note':sync['path'],'transcript':'','segments':segments if segments is not None else case.get('segments',[]),'transcript_edited':segments is None}
    core.update_record(case['id'],changes)
    return {'note':sync,'conflict':False}

def transcript(case):
    if case.get('transcript_note'):
        import re
        return re.sub(r'^---\n.*?\n---\n\n','',core.note_read(case['transcript_note']),flags=re.S)
    return case.get('transcript','')

def draft_version(case_id,product_id,content,task_id=None,parent_id=None,title=None):
    generation={}
    if task_id:
        existing=next((d for d in core.records('draft') if d.get('task_id')==task_id),None)
        if existing:return existing
    if title is None and parent_id:
        title=note_layout.draft_title(core.get(parent_id,'draft'))
    if title is None and task_id:
        title=task_get(task_id)['payload'].get('draft_name','')
    if task_id:
        payload=task_get(task_id)['payload']
        if task_get(task_id)['kind']=='local_write':
            generation={'requested_models':payload.get('model_selection',{}),
                        'generation_models':[{'model':payload.get('model_selection',{}).get('text_model'),'role':'writer'}],
                        'writing_mode':payload.get('writing_mode','生活分享'),'engine':'local'}
        if payload.get('model_runtime'):
            generation={'requested_models':payload.get('model_selection',{}),
                        'generation_models':payload.get('actual_models',[]),
                        'workflow_version_id':payload['model_runtime']['workflow_id']}
        if payload.get('fact_check'):
            generation.update(fact_check=payload['fact_check'],grounding_hash=payload['fact_check']['grounding_hash'])
        if payload.get('learning_entries'):
            generation['learning_entries']=payload['learning_entries']
        if payload.get('structure_reference'):
            generation['structure_reference']=payload['structure_reference']
        if payload.get('author'):
            generation.update(author=author_profiles.public(payload['author']),writing_mode=payload['writing_mode'],
                              requested_models=payload.get('model_selection',{}))
    elif parent_id:
        parent=core.get(parent_id,'draft')
        generation={k:parent[k] for k in ('author','writing_mode','grounding_hash','requested_models','structure_reference') if k in parent}
        if parent.get('fact_check'):generation['fact_check']={'status':'human_edited','parent_draft_id':parent_id}
    title=(title or '').strip() or note_layout.draft_title({'case_id':case_id})
    # A comma is a paragraph break for generated scripts and newly saved revisions.
    content=spoken.markdown_lines(spoken.format_spoken(content))
    id=core.uid()
    sync=core.sync_note('原创文案',id,title,content,{'case_id':case_id,'product_id':product_id,'parent_id':parent_id,'task_id':task_id,**generation})
    d=core.put('draft',{'title':title,'case_id':case_id,'product_id':product_id,'note':sync,'task_id':task_id,'parent_id':parent_id,'layout_version':spoken.LAYOUT_VERSION,**generation},id)
    note_layout.refresh_indexes()
    return d

def finish_copy(task,content):
    existing=next((d for d in core.records('draft') if d.get('task_id')==task['id']),None)
    if existing:return existing
    payload=task['payload'];product=core.get(payload['product_id'],'product')
    if not payload.get('grounding') and not product.get('note'):
        raise ValueError('历史任务缺少产品事实资料，不能直接恢复为正式文案，请补充产品资料后重新核对')
    grounding=payload.get('grounding') or writing_guard.snapshot(product['name'],products.dify_material(product))
    model=(payload.get('model_selection') or core.settings())['text_model']
    def progress(stage,value):task_update(task['id'],stage=stage,progress=value)
    content,report=writing_guard.protect(content,grounding,model,task['id'],progress,
        payload.get('inputs',{}).get('extra_requirements',''),payload.get('author'),payload.get('writing_mode','生活分享'))
    latest=task_get(task['id'])['payload']
    task_update(task['id'],payload=core.dumps({**latest,'fact_check':report}))
    return draft_version(payload.get('case_id',task['resource_id']),product['id'],content,task['id'])

def work(task):
    id=task['id']; payload=task['payload']; resource=task['resource_id']
    def progress(stage,value): task_update(id,stage=stage,progress=value)
    if core.STANDALONE and not core.DESKTOP and task['kind'] != 'learning_sync':
        from . import local_setup
        state = local_setup.status()
        while state['phase'] in ('preparing', 'downloading'):
            progress(state['stage'], 0.01)
            if STOP.wait(1): raise ValueError('服务正在停止，请重启后重试任务')
            state = local_setup.status()
        if state['phase'] == 'error': raise ValueError(state['error'])
    if task['kind']=='learning_sync':
        return writing_learning.sync(resource,payload['revision'])
    if task['kind'] in ('author_write','local_write'):
        existing=next((d for d in core.records('draft') if d.get('task_id')==id),None)
        if existing:return {'draft_id':existing['id'],'note':existing['note'],'fact_check':existing.get('fact_check')}
        profile=payload['author'];model=payload['model_selection']['text_model']
        progress('按'+profile['name']+' · '+payload['writing_mode']+'写作' if profile else '根据产品资料与参考架构写作',.15)
        content=writing_guard.generate(model,payload['grounding'],payload['inputs']['extra_requirements'],profile,payload['writing_mode'],structure_reference=payload.get('structure_reference'))
        draft=finish_copy(task,content)
        return {'draft_id':draft['id'],'note':draft['note'],'fact_check':draft['fact_check']}
    if task['kind']=='product_analysis':
        return products.analyze(task,progress)
    if task['kind']=='fetch_cover':
        progress('获取原视频封面',.1)
        path=covers.acquire(resource)
        return {'case_id':resource,'cover':str(path.relative_to(core.media_root())),'note':case_note(core.get(resource))}
    if task['kind']=='metadata':
        case=core.get(resource,'case')
        progress('读取原视频作者、时长与公开指标',.1)
        source_metadata.apply(resource,source_metadata.fetch(case['source_url']))
        return {'case_id':resource,'note':case_note(core.get(resource))}
    if task['kind']=='research_all':
        case=core.get(resource,'case')
        if not transcript(case).strip():
            if case.get('video'):work({**task,'kind':'process'})
            elif case.get('source_url'):work({**task,'kind':'link'})
            else:raise ValueError('缺少文案或视频链接，请先补充研究素材')
        completed=list((task.get('result') or {}).get('completed',[]))
        failures={}
        skipped={}
        for index,kind in enumerate(('video','title','cover_visual')):
            if kind in completed:continue
            if core.STANDALONE:
                current=core.get(resource,'case')
                if kind=='title' and not (current.get('publication_caption') or current.get('publication_hashtags')):
                    skipped[kind]='没有原始发布文案或话题，可补充后单独分析'
                elif kind=='video' and not transcript(current).strip():
                    skipped[kind]='视频没有口播逐字稿，可手动补充后分析'
                elif kind=='cover_visual' and not (current.get('cover') or current.get('source_url')):
                    skipped[kind]='没有封面图片，可上传封面后分析'
                if kind in skipped:continue
            progress({'video':'文案研究','title':'标题研究','cover':'封面提示词','cover_visual':'封面研究'}[kind]+' · 分析中',(index+1)/4)
            try:
                work({**task,'kind':'analysis','payload':{'type':kind},'research_label':{'video':'文案研究','title':'标题研究','cover':'封面提示词','cover_visual':'封面研究'}[kind]+' · 本地模型分析中','research_progress':(index+1)/4})
                completed.append(kind)
            except ValueError as e:
                failures[kind]=str(e)
            task_update(id,result=core.dumps({'completed':completed,'failures':failures,'skipped':skipped}))
        if failures:
            names={'video':'文案研究','title':'标题研究','cover':'封面提示词','cover_visual':'封面研究'}
            raise ValueError('；'.join(names[k]+'：'+v for k,v in failures.items()))
        if not completed:raise ValueError('尚无可分析的口播或图片，请补充资料')
        return {'case_id':resource,'completed':completed,'skipped':skipped}
    if task['kind'] in ('process','link'):
        case=core.get(resource,'case')
        if task['kind']=='link':
            remote_id=task.get('remote_task_id') or core.uid()
            task_update(id,remote_task_id=remote_id)
            progress('连接现有 Dify 视频获取服务',.05)
            try:
                result=bilinote.acquire(case['source_url'],case['title'],remote_id,progress,submit=not bool(task.get('remote_task_id')))
            except bilinote.AcquisitionConnectionError as e:
                # No POST was attempted: this ID cannot represent a remotely accepted run.
                # Ambiguous POST/poll failures retain the ID and must never auto-resubmit.
                if e.submission_not_attempted:task_update(id,remote_task_id=None)
                raise
            existing=core.get(resource)
            if existing.get('publication_source')!='人工补充或校对':core.update_record(resource,bilinote.publication_metadata(result))
            try:source_metadata.apply(resource,source_metadata.fetch(case['source_url']))
            except ValueError as e:core.update_record(resource,{'metadata_error':str(e)})
            raw=result['transcript']; segments=raw.get('segments') or []
            text=raw.get('full_text') or '\n'.join(s['text'] for s in segments)
            saved=save_transcript(case,text,segments)
            if saved['conflict']:raise ValueError('逐字稿存在人工修改，新内容已保存为冲突副本')
            core.update_record(resource,{'processing_status':'ready','ingestion':{
                'service':'BiliNote','task_id':remote_id,'collected_at':core.now(),
                'source_url':case['source_url'],'method':'既有 Dify 链接工作流同款 API'},
                'duration':max((float(s.get('end',0)) for s in segments),default=0) or None})
            return {'case_id':resource,'note':case_note(core.get(resource))}
        else: path=core.contained(core.media_root(),case['video'])
        progress('检查视频并提取关键帧',.1)
        info,frames,audio=media.extract(path,progress)
        core.update_record(resource,{**info,'frames':frames,'cover':frames[0]['path'],'processing_status':'frames_ready'})
        if info['has_audio']:
            segments=media.transcribe(audio,progress)
            result=save_transcript(core.get(resource),'\n'.join(f"[{s['start']:.2f}–{s['end']:.2f}] {s['text']}" for s in segments),segments)
            if result['conflict']: raise ValueError('逐字稿已被人工修改，新转写保存为冲突副本，请人工处理')
        core.update_record(resource,{'processing_status':'ready'})
        sync=case_note(core.get(resource))
        return {'case_id':resource,'note':sync}
    if task['kind']=='analysis':
        kind=payload['type']; image=None
        if resource:
            case=core.get(resource,'case')
            material={'publication_caption':case.get('publication_caption',''),'transcript':transcript(case),'segments':case.get('segments',[]),'metrics':case.get('metrics',{}),'timing_notice':'逐字稿经过人工编辑，segments 仅代表原始转写，不能将原始时间戳套给新文本' if case.get('transcript_edited') else '原始转写时间戳'}
            if kind=='title':
                material={'publication_caption':case.get('publication_caption',''),
                    'hashtags':case.get('publication_hashtags',[]),'raw_publication_text':case.get('publication_raw',''),
                    'metadata_source':case.get('publication_source','未知'),
                    'scope':'仅研究实际发布文案和经核实的#话题标签；不研究 item_title 或案例名称，不把口播逐字稿当发布文案。缺失项明确未知，标签合并歧义不得猜测'}
                if not any((material['publication_caption'],material['hashtags'])):raise ValueError('尚未取得原视频发布文案或#话题，请先刷新视频信息或补充原文')
            if kind=='cover':material,image=cover_prompts.material(case,transcript(case))
            if kind=='cover_visual':
                progress('获取原视频封面',.1)
                image=core.contained(core.media_root(),case['cover']) if case.get('cover') else covers.acquire(resource)
                material={'publication_caption':case.get('publication_caption',''),'scope':'仅分析实际封面可见内容，解释可能吸引注意的设计，不以点赞量推断因果或保证爆款','cover_source':core.get(resource).get('cover_provenance',{})}
            if kind=='video' and not material['transcript'].strip():raise ValueError('请先转写或手动录入文案')
        else: material=payload.get('material',{})
        progress(task.get('research_label','本地模型分析中，保留全部历史版本'),task.get('research_progress',.2))
        model,result=ai.analyze(kind,material,image)
        if kind=='cover':result=cover_prompts.assemble(result,material)
        if kind=='title':result['已核验原始话题标签']=material.get('hashtags',[])
        a=core.put('analysis',{'case_id':resource,'type':kind,'model':model,'prompt_version':ai.PROMPT_VERSION,
            'source':material,'source_media':str(image) if image else None,'result':result,'parent_id':None,'human':False})
        folder,note_title=note_layout.analysis_location(a)
        sync=core.sync_note(folder,a['id'],note_title,
            '```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```',{'case_id':resource,'model':model,'prompt_version':ai.PROMPT_VERSION})
        core.update_record(a['id'],{'note':sync})
        if resource:
            note_layout.migrate()
            case_note(core.get(resource))
        return {'analysis_id':a['id'],'note':sync}
    if task['kind']=='dify':
        case=core.get(resource,'case'); product=core.get(payload['product_id'],'product'); mode=payload['mode']
        inputs=dict(payload['inputs'])
        selection=payload.get('model_selection') or {k:core.settings()[k] for k in ('text_model','vision_model')}
        progress('准备所选文字与视觉模型的 Dify 运行版本',.05)
        runtime=dify_models.prepare(mode,selection)
        task_update(id,payload=core.dumps({**payload,'model_selection':selection,'model_runtime':runtime}))
        progress('检查已发布 Dify 输入契约',.1)
        if mode=='prototype':
            text=transcript(case)
            if not text.strip(): raise ValueError('参考案例没有逐字稿，无法生成原型文件')
            path=core.DATA/'prototype-files'/f'{id}.md';path.parent.mkdir(exist_ok=True)
            path.write_text('# 原文转录\n\n'+text,encoding='utf-8')
            inputs['prototype_file']=dify.upload(mode,path)
        inputs['source_material']=(payload.get('grounding') or {}).get('product_facts',products.dify_material(product))
        # Runtime graph reuses the frozen product brief; never re-upload originals.
        if not runtime.get('product_reuse'):
            raise ValueError('Dify 尚未准备产品正文复用版本，请重新生成')
        inputs['product_files']=[]
        def ids(run_id,remote_id):
            values={}
            if run_id: values['run_id']=run_id
            if remote_id: values['remote_task_id']=remote_id
            if values:task_update(id,**values)
        outputs=dify.run(mode,inputs,progress,ids,runtime['workflow_id'])
        try:
            actual_models=dify_models.executed(mode,task_get(id).get('run_id'))
        except (ValueError,KeyError):
            actual_models=[]
        latest=task_get(id)['payload']
        task_update(id,payload=core.dumps({**latest,'actual_models':actual_models}))
        draft=finish_copy(task_get(id),outputs['final_copy'])
        return {'draft_id':draft['id'],'note':draft['note'],'fact_check':draft['fact_check']}
    raise ValueError('不支持的任务类型')

def worker():
    while not STOP.is_set():
        try: writing_learning.schedule()
        except (OSError,ValueError,sqlite3.Error): pass
        with core.db() as c:
            row=c.execute("SELECT id FROM tasks WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row: c.execute("UPDATE tasks SET status='running' WHERE id=? AND status='queued'",(row[0],))
        if not row: WAKE.wait(2);WAKE.clear();continue
        task=task_get(row[0])
        try:
            result=work(task)
            task_update(task['id'],status='succeeded',stage='已完成',progress=1,result=core.dumps(result))
            if task['kind']=='research_all':
                with core.db() as c:c.execute("UPDATE tasks SET status='superseded',stage='后续研究已完成，旧失败记录保留',updated_at=? WHERE resource_id=? AND kind='research_all' AND id!=? AND status IN ('failed','interrupted')",(core.now(),task['resource_id'],task['id']))
        except Exception as e:
            # Only actionable messages; no credentials, payloads or tracebacks in task logs.
            message='Obsidian 或本地存储目录没有权限，请检查系统设置' if isinstance(e,PermissionError) else str(e)[:600] if isinstance(e,ValueError) else f'处理失败（{type(e).__name__}），请检查输入文件与服务状态'
            task_update(task['id'],status='failed',stage='处理失败',error=message)
            if task['kind']=='learning_sync':
                with writing_learning.LOCK:
                    latest=core.get(task['resource_id'],'writing_feedback')
                    if latest['revision']==task['payload']['revision']:
                        core.update_record(latest['id'],{'sync_status':'failed','sync_error':message})

def start():
    STOP.clear();threading.Thread(target=worker,daemon=True,name='virallab-worker').start()
