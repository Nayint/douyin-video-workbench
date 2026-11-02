import { useEffect, useRef, useState, Fragment } from "react";
import { api, type Row } from "./api";
import { useDraftState } from "./useDraftState";
import "./WritingLearning.css";

const labels: Record<string,string> = { good:"这段好", bad:"这段不好", adjust:"需要调整", approved:"认可成稿", preference:"明确写作偏好", rewrite:"修改对照" };
const states: Record<string,string> = {pending:"已保存，待整理",synced:"已同步 Obsidian",failed:"同步失败",conflict:"Obsidian 有人工修改，待处理"};
const scopes: Record<string,string> = {draft:"仅这篇",author_mode:"本作者＋本模式",author:"本作者",category:"同类产品",global:"所有写作"};
type Form = {id?:string;start:number;end:number;quote:string;body_hash:string;rating:string;scope:string;reason:string;replacement:string};
const empty:Form={start:0,end:0,quote:"",body_hash:"",rating:"bad",scope:"global",reason:"",replacement:""};

export function WritingAnnotations({draft,onError,onNotice}:{draft:Row;onError:(e:unknown)=>void;onNotice:(s:string)=>void}) {
 const [data,setData]=useState<{body:string;body_hash:string;entries:Row[]}|null>(null);
 const [form,setForm]=useDraftState<Form>("annotation."+draft.id,empty);
 useEffect(()=>{
  if(!form.quote&&!form.reason&&!form.replacement)setForm({...form,rating:"bad",scope:"global"});
 },[]);
 const [busy,setBusy]=useState(false);
 const source=useRef<HTMLDivElement>(null);
 const skipClick=useRef(false);
 const reload=()=>api("/drafts/"+draft.id+"/feedback").then(setData);
 useEffect(()=>{let live=true; const load=()=>api("/drafts/"+draft.id+"/feedback").then(x=>{if(live)setData(x)}).catch(e=>{if(live)onError(e)});load();const t=setInterval(load,3000);return()=>{live=false;clearInterval(t)}},[draft.id]);
 const choose=(start:number,end:number)=>{if(!data)return;setForm({...empty,start,end,quote:Array.from(data.body).slice(start,end).join(""),body_hash:data.body_hash});};
 const selectedText=(finish=false)=>{
  const selection=window.getSelection();if(!data||!source.current||!selection||!selection.rangeCount||selection.isCollapsed)return;
  const range=selection.getRangeAt(0);if(!source.current.contains(range.startContainer)||!source.current.contains(range.endContainer))return;
  const before=range.cloneRange();before.selectNodeContents(source.current);before.setEnd(range.startContainer,range.startOffset);
  const start=Array.from(before.toString()).length,end=start+Array.from(range.toString()).length;
  choose(start,end);
  if(finish){skipClick.current=true;selection.removeAllRanges();}
 };
 async function save(all=false){if(!data)return;setBusy(true);try{
  const payload=all?{...empty,start:0,end:Array.from(data.body).length,quote:data.body,body_hash:data.body_hash,rating:"approved"}:form;
  await api("/drafts/"+draft.id+"/feedback","POST",payload);setForm(empty);await reload();onNotice("标注已保存，后台会自动同步到文案沉淀库");
 }catch(e){onError(e)}finally{setBusy(false)}}
 async function revoke(id:string){try{await api("/learning/"+id,"DELETE");if(form.id===id)setForm(empty);await reload()}catch(e){onError(e)}}
 let offset=0;
 return <div className="writing-annotations">
  <div>
   <p className="hint">点选一小段，或拖选连续几句话，再在旁边标记。短句换行只用于阅读，你也可以合并选中。</p>
   <div ref={source} className="annotation-source" onMouseDown={()=>{skipClick.current=false}} onMouseMove={e=>{if(e.buttons===1)selectedText()}} onMouseUp={()=>selectedText(true)} aria-label="可标注文案正文">{data?.body.split("\n").map((line,i,lines)=>{
    const start=offset,end=start+Array.from(line).length;offset=end+1;
    const marked=data.entries.filter(r=>!r.revoked&&r.body_hash===data.body_hash&&r.start<end&&r.end>start);
    const active=!!form.quote&&form.body_hash===data.body_hash&&form.start<end&&form.end>start;
    return <Fragment key={i}><span className={[marked.length?"marked-"+marked[0].rating:"",active?"annotation-selected":""].filter(Boolean).join(" ")} role="button" tabIndex={0}
      aria-label={"标注第"+(i+1)+"段："+line}
      onClick={()=>{if(skipClick.current){skipClick.current=false;return;}if(!window.getSelection()?.toString())choose(start,end)}}
      onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(start,end)}}}>{line}</span>{i<lines.length-1?"\n":""}</Fragment>;
   })}</div>
  </div>
  <aside className="annotation-sidebar" aria-label="文案标注栏">
   <h3>{form.id?"修改标注":"标记与沉淀"}</h3>
   <button disabled={!data||busy} onClick={()=>save(true)}>收藏整篇为认可成稿</button>
   {form.quote?<blockquote className="annotation-quote">{form.quote}</blockquote>:<p className="annotation-placeholder">先点选左边的一段文案</p>}
   <label>评价<select value={form.rating} onChange={e=>setForm({...form,rating:e.target.value})}>
    {["good","bad","adjust","preference"].map(k=><option key={k} value={k}>{labels[k]}</option>)}
   </select></label>
   <label>作用范围<select value={form.scope} onChange={e=>setForm({...form,scope:e.target.value})}>
    {Object.entries(scopes).map(([k,v])=><option key={k} value={k}>{v}</option>)}
   </select></label>
   <label>{form.rating==="preference"?"明确的写作要求（必填）":"为什么这样标记（选填）"}<textarea rows={3} maxLength={3000} value={form.reason} onChange={e=>setForm({...form,reason:e.target.value})} placeholder="例如：这句像在念参数，想换成具体场景"/></label>
   <label>我会这样说（选填）<textarea rows={3} maxLength={10000} value={form.replacement} onChange={e=>setForm({...form,replacement:e.target.value})}/></label>
   {data&&form.quote&&form.body_hash!==data.body_hash&&<p role="alert">正文已变化，请重新点选段落。</p>}
   <button className="primary" disabled={busy||!form.quote||form.body_hash!==data?.body_hash||form.rating==="preference"&&!form.reason.trim()} onClick={()=>save()}>{busy?"保存中…":"保存标注并沉淀"}</button>
   {form.quote&&<button onClick={()=>setForm(empty)}>取消本次选择</button>}
   <p className="hint">只标好坏也会保存；没有理由时不推断规则。“明确写作偏好”才作为明确要求。商品事实不跨产品迁移。</p>
   <h3>本篇标注</h3>
   {data?.entries.length===0&&<p>还没有标注</p>}
   {data?.entries.map(r=><section key={r.id} className="annotation-entry">
    <strong>{labels[r.rating]}{r.revoked?" · 已撤销":""}</strong><span>{scopes[r.scope]}</span>
    <p className="annotation-quote">{r.quote.slice(0,160)}</p>{r.reason&&<p>{r.reason}</p>}
    {r.conflicts?.length>0&&<p role="alert">同段存在相反评价，已暂停自动调用。请修改或撤销其中一条。</p>}<small>{states[r.sync_status]||r.sync_status}</small>{r.sync_error&&<p role="alert">{r.sync_error}</p>}
    {!r.revoked&&<div className="row gap"><button onClick={()=>setForm({id:r.id,start:r.start,end:r.end,quote:r.quote,body_hash:r.body_hash,rating:r.rating==="approved"||r.rating==="rewrite"?"adjust":r.rating,scope:r.scope,reason:r.reason||"",replacement:r.replacement||""})}>修改</button><button onClick={()=>revoke(r.id)}>撤销</button></div>}
    {["failed","conflict"].includes(r.sync_status)&&<button onClick={async()=>{try{await api("/learning/"+r.id+"/retry","POST");await reload()}catch(e){onError(e)}}}>重试同步（保留人工笔记）</button>}
   </section>)}
  </aside>
 </div>;
}

export function LearningShelf({onError}:{onError:(e:unknown)=>void}) {
 const [rows,setRows]=useState<Row[]>([]);
 const load=()=>api<Row[]>("/learning").then(setRows).catch(onError);
 useEffect(()=>{load()},[]);
 return <section className="learning-shelf"><h3>已沉淀的反馈与修改</h3><p className="hint">修改对照自动记录在这里；作用范围为“仅这篇”的条目不会用于新文案。你可以在标注栏里明确新的偏好。</p>
 <button onClick={load}>刷新沉淀状态</button>
 {!rows.length&&<p>还没有反馈。打开一篇文案，点击“逐段标注”。</p>}
 {rows.map(r=><article className="annotation-entry" key={r.id}><strong>{r.draft_title} · {labels[r.rating]}</strong><p>{r.revoked?"已撤销":scopes[r.scope]} · {states[r.sync_status]}</p><p className="annotation-quote">{r.quote.slice(0,250)}</p>{r.replacement&&<p>修改后：{r.replacement.slice(0,250)}</p>}<p>{r.reason||"未注明原因，不推断规则"}</p>{r.conflicts?.length>0&&<p>同段评价冲突，暂停自动调用</p>}{r.note?.uri&&<a href={r.note.uri}>查看 Obsidian 沉淀</a>}{!r.revoked&&<button onClick={async()=>{try{await api("/learning/"+r.id,"DELETE");load()}catch(e){onError(e)}}}>撤销此条经验</button>}</article>)}
 </section>
}
