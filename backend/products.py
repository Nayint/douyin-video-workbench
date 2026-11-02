"""Local product extraction; canonical editable body remains in Obsidian."""
import hashlib
import json
import re
import subprocess
import shutil
from pathlib import Path
import zipfile
from xml.etree import ElementTree
from pypdf import PdfReader
from . import core, ai, note_layout


def extract(path):
    if path.suffix.lower() in ('.txt','.md'):
        return path.read_text(encoding='utf-8-sig'), []
    if path.suffix.lower()=='.docx':
        with zipfile.ZipFile(path) as z:
            info=z.getinfo('word/document.xml')
            if info.file_size>5000000:raise ValueError('文档解压内容过大，请精简后上传')
            root=ElementTree.fromstring(z.read(info))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p',ns)), []
    if path.suffix.lower()=='.pdf':
        reader=PdfReader(path)
        if reader.is_encrypted:raise ValueError('PDF 已加密，请上传未加密版本')
        if len(reader.pages)>30:raise ValueError('PDF 最多支持30页，请拆分后上传')
        text='\n'.join(p.extract_text() or '' for p in reader.pages)
        if len(text.strip())>30:return text, []
        renderer=shutil.which('pdftoppm')
        if not renderer:
            bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm'
            if bundled.is_file():renderer=str(bundled)
        if not renderer:raise ValueError('扫描 PDF 需要本地 pdftoppm，请先上传图片或文字版 PDF')
        images=[]
        for index in range(len(reader.pages)):
            prefix=path.parent/(path.stem+'-page-'+str(index+1))
            try:
                subprocess.run([renderer,'-f',str(index+1),'-l',str(index+1),'-singlefile','-scale-to','1600','-png',str(path),str(prefix)],check=True,capture_output=True,timeout=30)
            except (OSError,subprocess.SubprocessError):raise ValueError('扫描 PDF 转图片失败，请上传清晰图片或文字版 PDF')
            images.append(prefix.with_suffix('.png'))
        return '',images
    return '',[path]


def dify_material(product):
    """Return the concise copywriting brief when present, without Obsidian metadata."""
    text=core.note_read(product['note']['path'])
    text=re.sub(r'^---\n.*?\n---\n\s*','',text,flags=re.S)
    brief=re.search(r'^## 文案创作简报\s*\n(.*?)(?=^#{1,2}\s|\Z)',text,flags=re.M|re.S)
    return brief.group(1).strip() if brief else text.strip()


def analyze(task,progress):
    p=core.get(task['resource_id'],'product'); payload=task['payload']
    original=core.note_read(p['note']['path']); digest=hashlib.sha256(original.encode()).hexdigest()
    sources=[original]; references=[]; recognitions=[]; model=None
    for index,f in enumerate(p.get('files',[])):
        progress('读取产品附件 '+str(index+1),.1)
        path=core.contained(core.media_root(),f['path']); text,images=extract(path)
        if len(text)>100000:raise ValueError('文档文字超过10万字，请精简后上传')
        if text:sources.append('附件 '+f['name']+'\n'+text)
        for image in images:
            progress('本地视觉识别 '+f['name'],.25)
            model,result=ai.analyze('product_image',{'文件':f['name']},image)
            recognitions.append({'file':f['path'],'model':model,'result':result,'image':str(image.relative_to(core.media_root()))})
            sources.append(json.dumps(result,ensure_ascii=False))
        references.append(f['path'])
    if sum(map(len,sources))>120000:raise ValueError('产品材料过长，请减少附件或内容')
    progress('本地模型整理产品资料',.65)
    model,result=ai.analyze('product',{'现有资料与附件':sources,'用户更新要求':payload.get('instruction',''),'规则':'只按明确资料更新；未知保留未知，不虚构用户经历或功效。输出正文为可用于文案创作的Markdown字符串，另附待确认信息。'})
    body=result.get('正文')
    if not isinstance(body,str) or not body.strip():raise ValueError('模型未返回产品正文，请重试')
    version=core.put('product_version',{'product_id':p['id'],'model':model,'prompt_version':ai.PROMPT_VERSION,'instruction':payload.get('instruction',''),'source_hash':digest,'source_body':original,'recognitions':recognitions,'source_files':references,'result':result,'task_id':task['id']})
    history=core.sync_note('产品资料/历史版本',version['id'],p['name']+' · 分析版本',body,{'product_id':p['id'],'model':model})
    core.update_record(version['id'],{'note':history})
    if hashlib.sha256(core.note_read(p['note']['path']).encode()).hexdigest()!=digest:
        raise ValueError('分析期间产品资料已修改，分析版本已保留，请核对后重新分析')
    sync=core.sync_note('产品资料',p['id'],p['name'],body,{'type':'product','model':model,'version_id':version['id']})
    if sync['status']=='conflict':raise ValueError('产品笔记存在人工修改，已保存冲突副本和分析版本，请人工合并')
    core.update_record(p['id'],{'note':sync,'analysis_status':'ready','latest_version':version['id'],'summary':body[:160]})
    note_layout.refresh_indexes()
    return {'product_id':p['id'],'version_id':version['id'],'note':sync}
