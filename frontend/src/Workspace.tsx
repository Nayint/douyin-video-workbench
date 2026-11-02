import { useDraftState } from "./useDraftState";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  Download,
  FlaskConical,
  LoaderCircle,
  PenLine,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { api, key, stamp, clean, media, type Row } from "./api";
import { Badge, Empty, JsonView } from "./components";
type Feedback = {
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
};
export const DEFAULT_CREATION_REQUIREMENTS =
  "只输出可直接口播的原创抖音文案，约45–60秒，用自然口语，逗号、句号、问号或叹号后换行，小段之间不留空行，长句由页面自然折行，不要写资料摘要、分析说明或功能清单。参考案例只借鉴结构和节奏，不复制原句，也不移植其商品事实。商品硬事实以产品资料为准；实际购买、使用、回购和亲友反馈只允许使用明确提供的真实经历。可以表达主观选品判断、感受性修辞和合理生活场景，不必逐字复述资料。不得编造价格、规格、成分、具体功效、销量或成交结果，不把分析说成爆款因果。聚焦一个具体场景，不逐项念出全部功能和运行依赖。";
const TASK_STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "生成中",
  succeeded: "已完成",
  failed: "失败",
  interrupted: "已中断",
};
function CreationTaskStatus({
  task,
  onError,
  onNotice,
}: Feedback & { task: Row }) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    if (task.status !== "succeeded") return;
    const timeout = window.setTimeout(() => setVisible(false), 6000);
    return () => window.clearTimeout(timeout);
  }, [task.status]);
  if (!visible) return null;
  const failed = ["failed", "interrupted"].includes(task.status);
  const complete = task.status === "succeeded";
  return (
    <div
      className={"creation-status " + (failed ? "creation-status-error" : "")}
      role={failed ? "alert" : "status"}
    >
      <div className="row gap">
        {failed ? (
          <span aria-hidden="true">!</span>
        ) : complete ? (
          <CheckCircle2 size={17} />
        ) : (
          <LoaderCircle size={17} className="spin" />
        )}
        <strong>
          {task.payload?.draft_name || "文案创作"} ·{" "}
          {TASK_STATUS_LABEL[task.status] || task.status}
        </strong>
      </div>
      {failed ? (
        <>
          <p>{task.error || "任务已中断，请查询执行状态。"}</p>
          <button
            onClick={() =>
              api("/tasks/" + task.id + "/resume", "POST")
                .then(() => onNotice(task.kind === "author_write" ? "已重新排队生成并核对事实" : "已查询远端运行状态"))
                .catch(onError)
            }
          >
            {task.kind === "author_write" ? "重新生成并核对" : "查询并恢复结果"}
          </button>
        </>
      ) : complete ? (
        <p>
          已保存到<a href="#/drafts">原创文案</a>，可在那里查看和修改。
        </p>
      ) : (
        <>
          <p>
            {task.status === "queued"
              ? "已排队，稍后开始生成。"
              : task.stage || "正在生成，完成后保存到原创文案。"}
          </p>
          <progress max={1} value={task.progress} aria-label="文案生成进度" />
        </>
      )}
    </div>
  );
}

function CreationResult({ task }: { task: Row }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const id = task.result?.draft_id;
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    setBody(""); setError("");
    fetch("/api/drafts/" + encodeURIComponent(id) + "/export?format=txt", {signal: controller.signal})
      .then(r => { if (!r.ok) throw Error("暂时无法读取已保存文案，请到原创文案查看。"); return r.text(); })
      .then(setBody).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [id]);
  return <article className="creation-result" aria-label="本次创作结果">
    <div className="result-saved"><CheckCircle2 size={18} />已保存到原创文案</div>
    <h3>{task.payload?.draft_name || "本次原创文案"}</h3>
    {task.result?.fact_check?.status === "passed" && <p className="hint">生成时已通过逐句事实核对</p>}
    {error ? <p role="alert">{error}</p> : body ? <p className="preserve result-excerpt">{body.slice(0, 560)}{body.length > 560 ? "…" : ""}</p> : <p role="status">正在读取已保存的文案…</p>}
    <a href="#/drafts" className="button primary">打开原创文案<ArrowUpRight size={15} /></a>
  </article>;
}

export function Creation({
  cases,
  tasks,
  initialCase,
  onError,
  onNotice,
}: Feedback & { cases: Row[]; tasks: Row[]; initialCase: string | null }) {
  const [products, setProducts] = useState<Row[]>([]);
  const [authors, setAuthors] = useState<Row[]>([]);
  const [references, setReferences] = useState<Row[]>([]);
  const [structureId, setStructure] = useDraftState("creation.structureId", "");
  const [authorId, setAuthor] = useDraftState("creation.authorId", "");
  const [writingMode, setWritingMode] = useDraftState("creation.writingMode", "生活分享");
  const [experience, setExperience] = useDraftState("creation.experience", "");
  const [caseId, setCase] = useDraftState("creation.caseId", initialCase || "");
  const [productId, setProduct] = useDraftState("creation.productId", "");
  const [draftName, setDraftName] = useDraftState("creation.draftName", "");
  const [requirements, setRequirements] = useDraftState("creation.requirements", "");
  const [preview, setPreview] = useState<any>(null);
  const [learningSelection, setLearningSelection] = useState<string[] | null>(null);
  const [learningOptions, setLearningOptions] = useState<Row[]>([]);
  useEffect(()=>{setLearningSelection(null);setLearningOptions([])},[authorId,writingMode,productId]);
  const submitButton = useRef<HTMLButtonElement>(null);
  const scrollAfterInspect = useRef(false);
  useEffect(() => {
    if (!preview || !scrollAfterInspect.current) return;
    scrollAfterInspect.current=false;
    const frame = requestAnimationFrame(() => {
      submitButton.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
        block: "center",
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [preview]);
  const [busyAction, setBusyAction] = useState<"inspect" | "generate" | "">("");
  const [submitted, setSubmitted] = useState(false);
  const [requestKey, setKey] = useState(key());
  const [sessionTaskIds, setSessionTaskIds] = useState<string[]>([]);
  const signature = tasks.map((t) => t.id + t.status).join();
  useEffect(() => {
    api<Row[]>("/products").then(setProducts).catch(onError);
    api<Row[]>("/authors").then(setAuthors).catch(onError);
    api<Row[]>("/creation/references").then(setReferences).catch(onError);
  }, []);
  useEffect(() => {
    const active = tasks
      .filter(
        (t) => ["dify", "author_write"].includes(t.kind) && ["queued", "running"].includes(t.status),
      )
      .map((t) => t.id);
    if (active.length)
      setSessionTaskIds((ids) => [...new Set([...ids, ...active])]);
  }, [signature]);
  useEffect(() => {
    setPreview(null);
    setKey(key());
    setSubmitted(false);
  }, [caseId, productId, draftName, requirements, authorId, writingMode, experience, structureId]);
  useEffect(() => { if (initialCase) setCase(initialCase); }, [initialCase]);
  const busy = !!busyAction;
  const ready = (!!authorId || references.some(c => c.id === caseId)) && !!productId && !!draftName.trim();
  const payload = {
    case_id: authorId ? structureId : caseId,
    author_id: authorId,
    writing_mode: writingMode,
    personal_experience: experience.trim(),
    learning_ids: learningSelection,
    product_id: productId,
    draft_name: draftName.trim(),
    mode: "prototype",
    extra_requirements: requirements.trim()
      ? DEFAULT_CREATION_REQUIREMENTS +
        "\n\n【本次文案要求】\n" + requirements.trim() +
        "\n本次要求中的时长、口吻、受众、侧重点及禁用词优先于上面的默认创作偏好；遵循真实产品资料和短句逐行、段间无空行的排版。仅借鉴参考案例的结构与节奏，将本次要求落实到最终文案正文。"
      : DEFAULT_CREATION_REQUIREMENTS,
    request_key: requestKey,
  };
  async function inspect() {
    scrollAfterInspect.current=true;
    setBusyAction("inspect");
    try {
      const result = await api("/dify/preview", "POST", payload);
      setPreview(result);setLearningOptions(result.learning_entries || []);
    } catch (e) {
      onError(e);
    } finally {
      setBusyAction("");
    }
  }
  async function toggleLearning(id: string, checked: boolean) {
    const selected: string[] = learningSelection ?? (preview?.learning_entries || []).map((r: Row)=>r.id);
    const ids = checked ? [...new Set([...selected,id])] : selected.filter(x=>x!==id);
    setBusyAction("inspect");
    try {
      const result=await api("/dify/preview","POST",{...payload,learning_ids:ids});
      setLearningSelection(ids);setPreview(result);
    } catch(e) {setPreview(null);onError(e);} finally {setBusyAction("");}
  }
  async function generate() {
    setBusyAction("generate");
    try {
      const task = await api<Row>("/dify/generate", "POST", {...payload, expected_models: preview?.model_selection, expected_input_hash: preview?.grounding?.hash});
      setSessionTaskIds((ids) => [...new Set([...ids, task.id])]);
      setSubmitted(true);
    } catch (e) {
      onError(e);
    } finally {
      setBusyAction("");
    }
  }
  const feedbackTasks = tasks.filter(
    (t) =>
      ["dify", "author_write"].includes(t.kind) &&
      (["queued", "running", "failed", "interrupted"].includes(t.status) ||
        sessionTaskIds.includes(t.id)),
  );
  const reference = references.find(c => c.id === caseId);
  const selectedProduct = products.find(p => p.id === productId);
  const selectedAuthor = authors.find(a => a.id === authorId);
  const completedTask = feedbackTasks.find(t => t.status === "succeeded" && t.result?.draft_id && t.request_key === requestKey && sessionTaskIds.includes(t.id));
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">FROM RESEARCH TO ORIGINAL</div>
          <h1>文案创作</h1>
          <p>作者决定表达风格，也可选择已分析视频的架构来组织文案。</p>
        </div>
      </div>
      <div className="creation-grid">
        <section className="panel">
          <h2>开始一次创作</h2>
          <div className="step">
            <span>第一步</span>
            <h3>选择写作风格</h3>
          </div>
          <label>
            作者风格
            <select value={authorId} onChange={e => setAuthor(e.target.value)}>
              <option value="">默认风格 · 参考案例</option>
              {authors.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </label>
          {selectedAuthor ? <>
            <label>
              文案方式
              <select value={writingMode} onChange={e => setWritingMode(e.target.value)}>
                {selectedAuthor.modes.map((mode: string) => <option key={mode} value={mode}>{mode}</option>)}
              </select>
            </label>
            <p className="hint">{selectedAuthor.name} · {selectedAuthor.modes.join(" / ")}</p>
            <label>
              参考视频架构（选填）
              <select value={structureId} onChange={e => setStructure(e.target.value)}>
                <option value="">不指定 · 按作者卡组织</option>
                {references.filter(c => c.has_structure).map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </label>
            <p className="hint">只借鉴所选视频的叙事架构，措辞和语气使用作者风格。这里只显示研究所内已完成视频分析的案例，排除作者蒸馏素材。</p>
          </> :
          <label>
            研究案例
            <select value={caseId} onChange={(e) => setCase(e.target.value)}>
              <option value="">请选择案例</option>
              {references.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>}
          {!selectedAuthor && <p className="hint">只显示研究所内的视频，不包含作者蒸馏素材。</p>}
          <div className="step">
            <span>第二步</span>
            <h3>选择产品资料</h3>
          </div>
          <label>
            真实产品资料
            <select
              value={productId}
              onChange={(e) => setProduct(e.target.value)}
            >
              <option value="">请选择产品</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          {!products.length && (
            <p className="hint">先在左侧“产品库”添加产品资料。</p>
          )}
          <div className="step">
            <span>第三步</span>
            <h3>给文案命名</h3>
          </div>
          <label>
            文案名称
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              maxLength={200}
              required
              placeholder="例如：ViralLab · 从收藏视频到创作一篇文案"
            />
          </label>
          <p className="hint">生成后，在“原创文案”中使用这个名称保存。</p>
          <label>
            个人真实体验（选填）
            <textarea rows={3} value={experience} onChange={e => setExperience(e.target.value)} maxLength={3000}
              placeholder="只填写确实发生的使用经历、感受和不足。没有亲测可留空，生成时不会代写使用经历。" />
          </label>
          <label>
            本次文案要求（选填）
            <textarea
              rows={5}
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              maxLength={3500}
              placeholder="例如：控制在30秒，面向第一次接触AI的带货商家；重点介绍产品库，语气自然，不要使用‘最牛’和‘神器’。"
            />
          </label>
          <p className="hint">可填写时长、口吻、目标人群、重点和禁用词。留空按默认方式创作，短句逐行，小段之间不留空行。</p>
          <button
            className="primary full"
            disabled={busy || !ready}
            onClick={inspect}
          >
            {busyAction === "inspect" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <ShieldCheck size={16} />
            )}
            {busyAction === "inspect" ? "正在核对…" : "核对创作资料"}
          </button>
        </section>
        <section className="panel">
          <div className="section-head compact">
            <h2>创作预览</h2>
          </div>
          {(selectedAuthor || reference || selectedProduct) && <div className="creation-source-pair" aria-label="本次创作素材">
            <div key={caseId} className="creation-source-card">
              {selectedAuthor ? <PenLine size={24} /> : reference?.cover ? <img src={media(reference.cover)} alt="参考视频封面" /> : <FlaskConical size={24} />}
              <span>{selectedAuthor ? "作者风格" : "参考案例"}</span><strong>{selectedAuthor?.name || reference?.title || "等待选择"}</strong>
            </div>
            <Plus className="source-plus" size={18} aria-hidden="true" />
            <div key={productId} className="creation-source-card">
              {selectedProduct?.files?.find((f: Row) => f.type === "image") ? <img src={media(selectedProduct.files.find((f: Row) => f.type === "image").path)} alt="产品图片" /> : <PenLine size={24} />}
              <span>产品资料</span><strong>{selectedProduct?.name || "等待选择"}</strong>
            </div>
          </div>}
          {completedTask ? <><CreationResult key={completedTask.id} task={completedTask} /><button className="text-button new-request" onClick={() => { setKey(key()); setSubmitted(false); }}>另开一次创作</button></> : preview ? (
            <>
              <div className="creation-preview-summary">
                <strong>{draftName.trim()}</strong>
                <span>
                  {selectedAuthor ? "作者风格：" + selectedAuthor.name + " · " + writingMode : "参考案例：" + reference?.title}
                </span>
                <span>
                  产品资料：{products.find((p) => p.id === productId)?.name}
                </span>
                {preview.structure_reference && <div aria-label="本次参考架构">
                  <span>架构来源：{preview.structure_reference.title}</span>
                  <p>{preview.structure_reference.steps.join(" → ")}</p>
                  <span>只参考以上顺序，使用{selectedAuthor?.name}的表达风格。</span>
                </div>}
                <span>本次文案要求：</span>
                <p className="preserve">{requirements.trim() || "未填写，使用默认创作要求。"}</p>
                <span>本次文字模型：{preview.model_selection?.text_model || "未确认"}</span>
                <div aria-label="本次应用的写作经验">
                  <strong>本次应用的写作经验</strong>
                  {!learningOptions.length && <p>暂无匹配的有效沉淀。可在原创文案旁标注或收藏成稿。</p>}
                  {learningOptions.map(r=><label key={r.id}>
                    <input type="checkbox" disabled={busy} checked={(learningSelection ?? preview.learning_entries.map((e:Row)=>e.id)).includes(r.id)} onChange={e=>toggleLearning(r.id,e.target.checked)}/>
                    {r.rating === "preference" ? "明确偏好" : r.rating === "bad" || r.rating === "adjust" ? "负面样本" : "参考样本"} · {r.title}
                    <span>{r.reason || r.quote.slice(0,100)}</span>
                  </label>)}
                  {!!learningOptions.length && <p className="hint">可逐条关闭。仅学习表达，不复用旧商品事实；候选推断不会变成强制禁令。</p>}
                </div>
                <span>保存前逐句核对产品事实；有无依据内容时先修订，仍未通过则不保存。</span>
                <span>自然感受和合理场景表达可以保留；核对重点是价格、规格、成分、具体功效和真实经历。</span>
                <details><summary>查看本次产品事实与真实体验</summary>
                  <p className="preserve">{preview.grounding?.product_facts}</p>
                  <p className="preserve">真实体验：{preview.grounding?.personal_experience || "未提供，不生成亲测经历。"}</p>
                </details>
              </div>
              <button
                className="primary"
                ref={submitButton}
                onClick={generate}
                disabled={busy || submitted}
              >
                <Play size={16} />
                {busyAction === "generate"
                  ? "正在提交…"
                  : submitted
                    ? "本次已提交"
                    : "开始生成文案"}
              </button>
              {submitted && (
                <button
                  className="text-button new-request"
                  onClick={() => {
                    setKey(key());
                    setSubmitted(false);
                  }}
                >
                  另开一次创作
                </button>
              )}
              <p className="hint creation-flow-help">
                生成结果统一保存到左侧“原创文案”，供后续查看、修改和导出。
              </p>
            </>
          ) : (
            <Empty>选好作者或案例，再选择产品并命名，核对资料后开始创作。</Empty>
          )}
        </section>
      </div>
      <div className="creation-feedback">
        {feedbackTasks.map((t) => (
          <CreationTaskStatus
            key={t.id}
            task={t}
            onError={onError}
            onNotice={onNotice}
          />
        ))}
      </div>
    </>
  );
}
export function Products({ onError, onNotice }: Feedback) {
  const [rows, setRows] = useState<Row[]>([]),
    [name, setName] = useState(""),
    [content, setContent] = useState("");
  const load = () => api<Row[]>("/products").then(setRows).catch(onError);
  useEffect(() => {
    load();
  }, []);
  async function add() {
    try {
      await api("/products", "POST", { name, content });
      setName("");
      setContent("");
      load();
      onNotice("已保存到 Obsidian 产品关联目录");
    } catch (e) {
      onError(e);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PRODUCT KNOWLEDGE</div>
          <h1>产品资料</h1>
          <p>
            保存可核实的规格、适用场景和产品事实。资料正文直接读取 Obsidian。
          </p>
        </div>
        <button
          onClick={() =>
            api("/products/import", "POST")
              .then((r) => {
                load();
                onNotice("已从授权目录导入 " + r.imported + " 份资料");
              })
              .catch(onError)
          }
        >
          <RefreshCw size={16} />从 Obsidian 导入
        </button>
      </div>
      <div className="creation-grid">
        <section className="panel">
          <h2>添加产品资料</h2>
          <label>
            产品名称
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：某款桌面收纳盒"
            />
          </label>
          <label>
            产品事实
            <textarea
              rows={12}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="写清材质、尺寸、用途、限制及信息来源；不要填未经证实的效果。"
            />
          </label>
          <button
            className="primary"
            disabled={!name || !content}
            onClick={add}
          >
            <Plus size={16} />
            保存产品资料
          </button>
        </section>
        <div className="stack">
          {rows.length ? (
            rows.map((p) => (
              <section className="panel" key={p.id}>
                <h2>{p.name}</h2>
                <p className="preserve">{clean(p.content)}</p>
                <div className="hint">{p.note.path}</div>
                <ul>
                  {(p.files || []).map((f: any) => (
                    <li key={f.path}>{f.name}</li>
                  ))}
                </ul>
                <label className="upload-inline">
                  <Upload size={15} />
                  添加产品附件（最多5个）
                  <input
                    type="file"
                    accept=".txt,.md,.pdf,.docx,.png,.jpg,.webp"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const f = new FormData();
                      f.append("file", file);
                      try {
                        await api("/products/" + p.id + "/files", "POST", f);
                        load();
                      } catch (e) {
                        onError(e);
                      }
                    }}
                  />
                </label>
              </section>
            ))
          ) : (
            <Empty>还没有产品资料</Empty>
          )}
        </div>
      </div>
    </>
  );
}
export function Research({
  onError,
  onNotice,
  tasks,
}: Feedback & { tasks: Row[] }) {
  const [text, setText] = useState(""),
    [product, setProduct] = useState(""),
    [reports, setReports] = useState<Row[]>([]),
    [titles, setTitles] = useState<Row[]>([]),
    [category, setCategory] = useState(""),
    [structure, setStructure] = useState("");
  const load = () =>
    Promise.all([api<Row[]>("/analyses"), api<Row[]>("/titles")])
      .then(([a, t]) => {
        setReports(
          a.filter((r) => ["title", "compare", "suggest"].includes(r.type)),
        );
        setTitles(t);
      })
      .catch(onError);
  useEffect(() => {
    load();
  }, [tasks.map((t) => t.id + t.status).join()]);
  async function run(type: string) {
    try {
      if (!text.trim() && type !== "suggest") throw Error("请先输入标题");
      await api("/research", "POST", {
        type,
        request_key: key(),
        material:
          type === "suggest"
            ? { product, reference_titles: text.split("\n").filter(Boolean) }
            : { titles: text.split("\n").filter(Boolean) },
      });
      onNotice("本地标题研究任务已加入队列");
    } catch (e) {
      onError(e);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORDS THAT OPEN A STORY</div>
          <h1>标题研究</h1>
          <p>比较标题怎样表达利益、情绪和悬念，积累可以验证的写法。</p>
        </div>
        <Badge>Ollama 本地生成</Badge>
      </div>
      <div className="creation-grid">
        <section className="panel">
          <h2>单条分析 / 多标题比较</h2>
          <label>
            参考标题（每行一条）
            <textarea
              rows={7}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="输入一条标题，或粘贴多条标题进行比较"
            />
          </label>
          <p className="hint">
            字数：
            {text
              .split("\n")
              .filter(Boolean)
              .map((t) => Array.from(t).length)
              .join(" / ") || "—"}
            （包含标点）
          </p>
          <div className="row gap">
            <button
              className="primary"
              onClick={() =>
                run(
                  text.split("\n").filter(Boolean).length > 1
                    ? "compare"
                    : "title",
                )
              }
            >
              <FlaskConical size={16} />
              开始研究
            </button>
            <button
              onClick={async () => {
                try {
                  for (const title of text.split("\n").filter(Boolean))
                    await api("/titles", "POST", {
                      title,
                      category,
                      structure,
                    });
                  load();
                  onNotice("标题已收藏");
                } catch (e) {
                  onError(e);
                }
              }}
            >
              保存优秀标题
            </button>
          </div>
          <div className="two-input">
            <label>
              行业 / 主题
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              />
            </label>
            <label>
              结构分类
              <input
                value={structure}
                onChange={(e) => setStructure(e.target.value)}
              />
            </label>
          </div>
          <label>
            为产品生成原创标题
            <textarea
              rows={4}
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="输入真实产品资料及希望表达的重点"
            />
          </label>
          <button disabled={!product.trim()} onClick={() => run("suggest")}>
            <PenLine size={16} />
            生成原创标题建议
          </button>
        </section>
        <section className="panel">
          <h2>优秀标题收藏</h2>
          {titles.length ? (
            titles.map((t) => (
              <div className="saved-title" key={t.id}>
                <strong>{t.title}</strong>
                <div className="row gap">
                  <Badge>{t.category || "未分类"}</Badge>
                  <span className="muted">{t.structure || "结构待研究"}</span>
                </div>
              </div>
            ))
          ) : (
            <Empty>把值得借鉴的标题保留下来。</Empty>
          )}
        </section>
      </div>
      <div className="section-head">
        <h2>研究报告与比较结果</h2>
        <span className="muted">保留全部分析版本</span>
      </div>
      {reports.length ? (
        reports.map((r) => (
          <details className="panel report" key={r.id}>
            <summary>
              {
                {
                  title: "标题分析",
                  compare: "案例 / 标题比较",
                  suggest: "原创标题建议",
                }[r.type as string]
              }{" "}
              · {stamp(r.created_at)} · {r.model}
            </summary>
            <JsonView value={r.result} />
            {r.note?.uri && (
              <a className="note-link" href={r.note.uri}>
                在 Obsidian 打开
                <ArrowUpRight size={14} />
              </a>
            )}
          </details>
        ))
      ) : (
        <Empty>完成分析后，报告会显示在这里。</Empty>
      )}
    </>
  );
}
export function SettingsPage({
  onError,
  onNotice,
  tasks,
}: Feedback & { tasks: Row[] }) {
  const [cfg, setCfg] = useState<any>(null),
    [connection, setConnection] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [backup, setBackup] = useState<any>(null),
    [modelList, setModelList] = useState<Row[]>([]),
    [modelError, setModelError] = useState(""),
    [savedModels, setSavedModels] = useState<any>(null);
  useEffect(() => {
    api("/settings")
      .then((r) => {
        setCfg(r);
        setSavedModels(r);
        refreshModels(r.ollama_url);
      })
      .catch(onError);
  }, []);
  async function refreshModels(url: string) {
    setModelError("");
    setBusy(true);
    try {
      const r = await api("/models", "POST", { ollama_url: url });
      setModelList(r.models);
    } catch (e) {
      setModelList([]);
      setModelError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveSettings() {
    setBusy(true);
    try {
      await api("/settings", "PUT", cfg);
      const actual = await api("/settings");
      if (
        actual.text_model !== cfg.text_model ||
        actual.vision_model !== cfg.vision_model ||
        actual.ollama_url !== cfg.ollama_url
      )
        throw new Error("模型配置回读不一致，请重新保存");
      setCfg(actual);
      setSavedModels(actual);
      onNotice("设置已保存并核对，新分析和 Dify 文案创作使用所选模型");
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  async function test() {
    setBusy(true);
    try {
      setConnection(await api("/connections"));
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  if (!cfg) return <Empty>正在读取设置…</Empty>;
  const field = (name: string, label: string, type = "text") => (
    <label>
      {label}
      <input
        type={type}
        value={cfg[name] ?? ""}
        onChange={(e) =>
          setCfg({
            ...cfg,
            [name]: type === "number" ? Number(e.target.value) : e.target.value,
          })
        }
      />
    </label>
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">LOCAL & CONNECTED</div>
          <h1>系统设置</h1>
          <p>连接现有服务，管理本地数据与任务。</p>
        </div>
        <button className="primary" disabled={busy} onClick={saveSettings}>
          <Save size={16} />
          保存设置
        </button>
      </div>
      <div className="creation-grid">
        <section className="panel">
          <h2>Dify 工作流</h2>
          {field("dify_url", "Dify API 地址")}
          {field("bilinote_url", "现有 BiliNote 视频服务地址")}
          {field(
            "prototype_api_key",
            "原型 Markdown 工作流 API Key（留空保留）",
            "password",
          )}
          {field(
            "link_api_key",
            "视频链接工作流 API Key（留空保留）",
            "password",
          )}
          <p className="hint">
            已配置：
            {Object.entries(cfg.dify_workflows || {})
              .filter(([, v]: any) => v.configured)
              .map(([k]) => (k === "prototype" ? "原型工作流" : "链接工作流"))
              .join("、") || "暂无"}
            。密钥只由后端读取，不返回浏览器。
          </p>
          <h2>Ollama 本地模型</h2>
          {field("ollama_url", "Ollama 地址")}
          <p className="hint">
            按本机模型实际能力分类；多模态模型可同时用于文字和图片。仅切换已安装模型。
            Dify 文案创作也跟随此处选择，保存时准备独立运行版本，保留原工作流。
          </p>
          {(
            [
              ["text_model", "文字分析与文案生成模型", "text"],
              ["vision_model", "图片识别与封面视觉模型", "vision"],
            ] as const
          ).map(([setting, label, cap]) => (
            <label key={setting}>
              {label}
              <select
                value={cfg[setting]}
                disabled={busy || !modelList.length}
                onChange={(e) => setCfg({ ...cfg, [setting]: e.target.value })}
              >
                {!modelList.some((m) => m.name === cfg[setting] && m[cap]) && (
                  <option value={cfg[setting]}>
                    {cfg[setting]}（当前配置，能力未确认）
                  </option>
                )}
                {modelList
                  .filter((m) => m[cap])
                  .map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}
                      {m.vision ? " · 多模态" : " · 文字"}
                    </option>
                  ))}
              </select>
            </label>
          ))}
          <button disabled={busy} onClick={() => refreshModels(cfg.ollama_url)}>
            刷新本机模型
          </button>
          {modelError && (
            <p role="alert" className="error-text">
              {modelError}
            </p>
          )}
          {savedModels && (
            <p className="hint">
              当前已生效：文字 {savedModels.text_model}；视觉{" "}
              {savedModels.vision_model}
              。新任务读取此配置，正在执行的推理保持原模型。
            </p>
          )}
          {Object.entries(savedModels?.dify_model_status || {}).map(([mode, info]: [string, any]) => (
            <p className="hint" key={mode}>
              Dify {mode === "prototype" ? "文案创作" : "链接工作流"}已准备：文字 {info.text_model}；图片 {info.vision_model}。
            </p>
          ))}
          {field("model_timeout", "模型超时（秒）", "number")}
          <button disabled={busy} onClick={test}>
            <RefreshCw className={busy ? "spin" : ""} size={16} />
            测试连接与读取模型列表
          </button>
          {connection && (
            <div className="connections">
              {Object.entries(connection).map(([k, v]: any) => (
                <div key={k}>
                  <span>
                    {v.ok ? "✓" : "!"} {k}
                  </span>
                  <span className={v.ok ? "good" : "error-text"}>
                    {v.ok ? "可用" : v.error || "目录无权限或模型缺失"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <h2>存储与视频处理</h2>
          {field("vault_path", "现有 Obsidian Vault 路径")}
          {field("vault_subdir", "授权研究子目录")}
          {field("product_subdir", "授权产品资料子目录")}
          {field("storage_path", "本地媒体存储路径")}
          {field("whisper_model", "已有 faster-whisper 模型目录")}
          {field("max_upload_mb", "上传大小上限（MB）", "number")}
          {field("frame_count", "关键帧数量", "number")}
          <p className="hint">
            不会自动下载模型。转写使用已有模型文件，封面分析会先确认模型支持视觉。
          </p>
          <h2>备份与恢复</h2>
          <p className="hint">
            备份 SQLite、媒体、ViralLab
            笔记及凭据。文件只保存在本机，请妥善保管。恢复会保留冲突笔记副本。
          </p>
          <button
            onClick={() =>
              api("/backups", "POST")
                .then((r) => {
                  setBackup(r);
                  onNotice("本机备份完成");
                })
                .catch(onError)
            }
          >
            <Download size={16} />
            创建完整备份
          </button>
          {backup && (
            <a className="note-link" href={backup.url}>
              下载备份 {backup.filename}
            </a>
          )}
          <p className="hint">恢复：先停止工作台，再在项目目录运行</p>
          <code>.venv/bin/python scripts/restore.py backups/备份.zip</code>
        </section>
      </div>
      <div className="section-head">
        <h2>任务日志</h2>
        <span className="muted">仅记录状态，不记录密钥</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>任务</th>
              <th>状态</th>
              <th>当前阶段 / 错误</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{stamp(t.created_at)}</td>
                <td>{t.kind}</td>
                <td>
                  <Badge>{t.status}</Badge>
                </td>
                <td>{t.error || t.stage}</td>
                <td>
                  {["failed", "interrupted"].includes(t.status) && (
                    <button
                      onClick={() =>
                        api("/tasks/" + t.id + "/resume", "POST")
                          .then(() => onNotice("已查询状态或重试"))
                          .catch(onError)
                      }
                    >
                      重试 / 查询
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
