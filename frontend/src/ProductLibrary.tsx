import { useDraftState } from "./useDraftState";
import { ArrowUpRight, Layers, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, key, clean, stamp, media, type Row } from "./api";
import { Empty } from "./components";
import { ResearchDialog, type CardOrigin } from "./ResearchDialog";

type Props = {
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
  tasks: Row[];
};
export function ProductLibrary({ onError: reportError, onNotice: reportNotice, tasks }: Props) {
  const cardOrigin = useRef<CardOrigin | null>(null);
  const [detailMessage, setDetailMessage] = useState<{ text: string; error: boolean } | null>(null);
  function onError(error: unknown) {
    setDetailMessage({ text: error instanceof Error ? error.message : String(error), error: true });
    reportError(error);
  }
  function onNotice(text: string) {
    setDetailMessage({ text, error: false });
    reportNotice(text);
  }
  const [rows, setRows] = useState<Row[]>([]),
    [name, setName] = useDraftState("products.name", ""),
    [text, setText] = useDraftState("products.text", ""),
    [files, setFiles] = useDraftState<File[]>("products.files", [], false),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useDraftState("products.selected", ""),
    [instruction, setInstruction] = useDraftState("products.instruction", ""),
    [versions, setVersions] = useState<Row[]>([]),
    [context, setContext] = useState<{
      id: string;
      x: number;
      y: number;
    } | null>(null),
    [removed, setRemoved] = useState<Row | null>(null),
    [deleting, setDeleting] = useState(false);
  const contextTrigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!context) return;
    const close = () => setContext(null);
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setContext(null);
        contextTrigger.current?.focus();
      }
    };
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", escape);
    };
  }, [context]);
  const signature = tasks
    .filter((t) => t.kind === "product_analysis")
    .map((t) => t.id + t.status)
    .join();
  const load = () => api<Row[]>("/products").then(setRows).catch(onError);
  useEffect(() => {
    load();
  }, [signature]);
  useEffect(() => {
    if (selected)
      api<Row[]>("/products/" + selected + "/versions")
        .then(setVersions)
        .catch(onError);
  }, [selected, signature]);
  const product = rows.find((p) => p.id === selected);
  function openContext(
    id: string,
    x: number,
    y: number,
    target: HTMLButtonElement,
  ) {
    contextTrigger.current = target;
    setContext({
      id,
      x: Math.max(8, Math.min(x, window.innerWidth - 208)),
      y: Math.max(8, Math.min(y, window.innerHeight - 64)),
    });
  }
  async function remove(id: string) {
    setContext(null);
    setDeleting(true);
    try {
      const p = rows.find((p) => p.id === id);
      await api("/products/" + id, "DELETE");
      setRows((old) => old.filter((p) => p.id !== id));
      if (selected === id) setSelected("");
      if (p) setRemoved(p);
    } catch (e) {
      onError(e);
    } finally {
      setDeleting(false);
    }
  }
  async function undoRemove() {
    if (!removed) return;
    setDeleting(true);
    try {
      await api("/products/" + removed.id + "/restore", "POST");
      await load();
      setRemoved(null);
      onNotice("产品已恢复");
    } catch (e) {
      onError(e);
    } finally {
      setDeleting(false);
    }
  }
  async function run(id: string, update = "") {
    await api("/products/" + id + "/analyze", "POST", {
      instruction: update,
      request_key: key(),
    });
    onNotice("已开始本地产品分析，完成后自动保存");
  }
  async function create(analyze: boolean) {
    setBusy(true);
    try {
      const p = await api<Row>("/products", "POST", {
        name,
        content:
          text.trim() ||
          (files.length
            ? "待分析附件：" + files.map((f) => f.name).join("、")
            : ""),
      });
      cardOrigin.current = null;
      setDetailMessage(null);
      setSelected(p.id);
      await load();
      for (const file of files) {
        const data = new FormData();
        data.append("file", file);
        await api("/products/" + p.id + "/files", "POST", data);
      }
      if (analyze) await run(p.id);
      else onNotice("产品资料已保存");
      setName("");
      setText("");
      setFiles([]);
      await load();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  const active = tasks.find(
    (t) => t.resource_id === selected && t.kind === "product_analysis",
  );
  const running = active && ["queued", "running"].includes(active.status);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PRODUCT LIBRARY</div>
          <h1>产品库</h1>
          <p>上传真实产品资料，本地分析整理，随时补充更新，用于文案创作。</p>
        </div>
        <button
          onClick={() =>
            api("/products/import", "POST")
              .then(load)
              .then(() => onNotice("已导入 Obsidian 产品资料"))
              .catch(onError)
          }
        >
          从 Obsidian 导入
        </button>
      </div>
      <section className="panel product-upload-panel">
        <div className="section-head compact">
          <h2>上传产品资料</h2>
        </div>
        <details className="product-analysis-flow">
          <summary>查看产品资料分析逻辑</summary>
          <ol>
            <li>保存输入文字和原始附件，建立产品记录。</li>
            <li>
              TXT、Markdown、DOCX 直接提取文字；PDF
              优先提取文本，扫描件转图片识别。
            </li>
            <li>
              图片交给设置中的本地视觉模型，识别可见文字、外观、规格与不确定项。
            </li>
            <li>
              将现有正文、附件内容、图片识别结果及更新要求交给本地文字模型，整理产品事实、规格、适用场景、卖点依据、限制与待确认信息。
            </li>
            <li>
              保存新的分析版本，检查人工修改冲突后更新 Obsidian
              产品正文，供后续文案创作读取。
            </li>
          </ol>
          <p className="muted">
            未知信息保留待确认，不从外观推断材质或功效；分析使用系统设置中已保存的模型。含文字和图片的
            PDF 当前优先读取文本，不保证识别其中所有图片。
          </p>
        </details>
        <label>
          产品名称
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="为这款产品起个名字"
          />
        </label>
        <div className="product-material-input">
          <label>
            产品资料
            <textarea
              rows={7}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="直接粘贴产品介绍，也可以在下方添加图片、文档或 PDF，支持混合提交。"
            />
          </label>
          <label className="product-file-picker">
            添加图片 / 文档 / PDF
            <input
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.webp,.txt,.md,.docx,.pdf"
              disabled={busy}
              onChange={(e) => {
                const added = Array.from(e.target.files || []);
                const merged = [...files];
                for (const file of added) {
                  if (!/\.(png|jpe?g|webp|txt|md|docx|pdf)$/i.test(file.name)) {
                    onError(
                      new Error("请选择图片、TXT、Markdown、DOCX 或 PDF 文件"),
                    );
                    continue;
                  }
                  if (file.size > 15 * 1024 * 1024) {
                    onError(new Error(file.name + " 超过15 MB，请精简后上传"));
                    continue;
                  }
                  if (
                    !merged.some(
                      (f) =>
                        f.name === file.name &&
                        f.size === file.size &&
                        f.lastModified === file.lastModified,
                    )
                  )
                    merged.push(file);
                }
                if (merged.length > 5) {
                  onError(new Error("最多添加5个文件，请先移除不需要的附件"));
                  e.target.value = "";
                  return;
                }
                setFiles(merged);
                e.target.value = "";
              }}
            />
          </label>
          <p className="muted">
            文字、图片、文档和 PDF 可一起提交，自动识别内容。最多5个附件，每个15
            MB。
          </p>
          {files.length > 0 && (
            <ul className="product-file-list">
              {files.map((f, index) => (
                <li key={f.name + index}>
                  <span>{f.name}</span>
                  <button
                    disabled={busy}
                    aria-label={"移除附件" + f.name}
                    onClick={() =>
                      setFiles(files.filter((_, i) => i !== index))
                    }
                  >
                    移除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="toolbar">
          <button
            disabled={busy || !name.trim() || (!text.trim() && !files.length)}
            onClick={() => create(false)}
          >
            仅保存资料
          </button>
          <button
            className="primary"
            disabled={busy || !name.trim() || (!text.trim() && !files.length)}
            onClick={() => create(true)}
          >
            {busy ? "正在上传…" : "分析并保存"}
          </button>
        </div>
      </section>
      <h2>我的产品 · {rows.length}</h2>
      {removed && (
        <div className="panel row gap product-delete-notice" role="status">
          <span>已删除“{removed.name}”，原始资料和已有文案保留。</span>
          <button disabled={deleting} onClick={undoRemove}>
            撤销删除
          </button>
        </div>
      )}
      <div className="product-cards">
        {rows.map((p) => (
          <button
            className={
              "panel product-card " + (selected === p.id ? "selected" : "")
            }
            key={p.id}
            data-material={
              p.files?.some((f: Row) => f.type === "image")
                ? "image"
                : p.files?.some((f: Row) => /\.pdf$/i.test(f.name))
                  ? "pdf"
                  : p.files?.length
                    ? "document"
                    : "text"
            }
            aria-label={"查看产品详情：" + p.name}
            aria-haspopup="dialog"
            onContextMenu={(e) => {
              e.preventDefault();
              e.stopPropagation();
              openContext(p.id, e.clientX, e.clientY, e.currentTarget);
            }}
            onKeyDown={(e) => {
              if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
                e.preventDefault();
                const rect = e.currentTarget.getBoundingClientRect();
                openContext(
                  p.id,
                  rect.left + 16,
                  rect.top + 40,
                  e.currentTarget,
                );
              }
            }}
            onClick={(e) => {
              const element = e.currentTarget;
              cardOrigin.current = { element, rect: element.getBoundingClientRect(), focus: element };
              setDetailMessage(null);
              setSelected(p.id);
              setInstruction("");
            }}
          >
            <span className="product-card-heading">
              <span className="product-card-symbol">
                <Layers size={20} />
              </span>
              <strong>{p.name}</strong>
              <span className="card-open-affordance" aria-hidden="true">
                <ArrowUpRight size={17} />
              </span>
            </span>
            {p.files?.some((f: Row) => f.type === "image") && (
              <span className="product-card-preview">
                <img
                  src={media(p.files.find((f: Row) => f.type === "image").path)}
                  alt={p.name + "产品图片"}
                  loading="lazy"
                />
              </span>
            )}
            <span className="muted">
              {tasks.some(
                (t) =>
                  t.resource_id === p.id &&
                  t.kind === "product_analysis" &&
                  ["queued", "running"].includes(t.status),
              )
                ? "分析中"
                : p.analysis_status === "ready"
                  ? "已分析"
                  : "待分析"}{" "}
              · {p.files?.length || 0} 个附件
            </span>
            <p>
              {clean(p.content)
                .replace(/^#{1,6}\s+/gm, "")
                .replace(/^\s*[-*]\s+/gm, "")
                .replace(/\s+/g, " ")
                .slice(0, 130)}
            </p>
            <span className="muted">{stamp(p.updated_at || p.created_at)}</span>
            <span className="product-card-open">查看产品资料与分析版本</span>
          </button>
        ))}
      </div>
      {!rows.length && <Empty>上传第一份产品资料，建立你的产品库。</Empty>}
      {context && (
        <div
          className="context-menu"
          role="menu"
          aria-label="产品操作"
          style={{ left: context.x, top: context.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            role="menuitem"
            autoFocus
            disabled={deleting}
            onClick={() => remove(context.id)}
          >
            <Trash2 size={16} />
            删除
          </button>
        </div>
      )}
      {product && (
        <ResearchDialog origin={cardOrigin.current} onClose={() => setSelected("")} label={"产品详情：" + product.name} closeLabel="关闭产品详情">
          {() => <div className="product-detail-content">
            {product.files?.some((f: Row) => f.type === "image") && (
              <div className="product-detail-gallery" aria-label="产品图片">
                {product.files.filter((f: Row) => f.type === "image").map((f: Row, index: number) => (
                  <figure key={f.path}>
                    <img src={media(f.path)} alt={f.name || product.name + "产品图片"} loading={index === 0 ? "eager" : "lazy"} />
                    <figcaption>{f.name}</figcaption>
                  </figure>
                ))}
              </div>
            )}
            <div className="page-heading product-detail-heading"><div><p>产品库</p><h1>{product.name}</h1></div></div>
            {detailMessage && <div className={"alert " + (detailMessage.error ? "error" : "success")} role={detailMessage.error ? "alert" : "status"}>{detailMessage.text}</div>}
            <div className="product-detail-meta">
              <span>
                {product.analysis_status === "ready" ? "已分析" : "待分析"}
              </span>
              <span>{product.files?.length || 0} 个原始附件</span>
              <span>
                更新于 {stamp(product.updated_at || product.created_at)}
              </span>
            </div>
            <h3>产品资料正文</h3>
            <p className="preserve product-detail-body">
              {clean(product.content)}
            </p>
            <h3>原始附件</h3>
            {product.files?.some((f: Row) => f.type !== "image") ? (
              <div className="product-attachments">
                {product.files.filter((f: Row) => f.type !== "image").map((f: Row) => (
                  <a
                    href={media(f.path)}
                    key={f.path}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span>{f.name}</span>
                  </a>
                ))}
              </div>
            ) : (
              <p className="muted">{product.files?.some((f: Row) => f.type === "image") ? "产品图片已展示在上方。" : "这份产品资料目前只有文字。"}</p>
            )}
            <label>
              追加产品附件（图片、文档或 PDF，累计最多5个）
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp,.txt,.md,.docx,.pdf"
                disabled={!!running}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const data = new FormData();
                  data.append("file", file);
                  try {
                    await api(
                      "/products/" + product.id + "/files",
                      "POST",
                      data,
                    );
                    await load();
                    onNotice("附件已添加，点击分析更新产品资料");
                  } catch (e) {
                    onError(e);
                  }
                  e.target.value = "";
                }}
              />
            </label>
            <label>
              补充或更新产品资料
              <textarea
                rows={4}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="例如：新增黑色款，尺寸改为……请保留其他已确认信息。"
              />
            </label>
            <div className="toolbar">
              <button
                className="primary"
                disabled={busy || !!running}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await run(product.id, instruction);
                    setInstruction("");
                  } catch (e) {
                    onError(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {running
                  ? "正在分析…"
                  : instruction.trim()
                    ? "用本地 AI 更新资料"
                    : "分析产品资料"}
              </button>
            </div>
            {active && (
              <div
                role="status"
                className={active.status === "failed" ? "error" : "hint"}
              >
                {active.stage}
                {active.error ? "：" + active.error : ""}
                {active.status === "failed" && (
                  <button
                    onClick={() =>
                      api("/tasks/" + active.id + "/resume", "POST")
                        .then(() => onNotice("已重试"))
                        .catch(onError)
                    }
                  >
                    重试分析
                  </button>
                )}
              </div>
            )}
            <details>
              <summary>历史分析版本（{versions.length}）</summary>
              {versions.map((v) => (
                <details key={v.id}>
                  <summary>
                    {stamp(v.created_at)} · {v.model}
                  </summary>
                  <p className="muted">
                    模型：{v.model} · 提示词：{v.prompt_version}
                  </p>
                  {v.instruction && <p>本次更新要求：{v.instruction}</p>}
                  <p className="preserve">{v.result?.正文}</p>
                  {v.result?.待确认信息?.length > 0 && (
                    <div>
                      <strong>待确认信息</strong>
                      <ul>
                        {v.result.待确认信息.map(
                          (info: string, index: number) => (
                            <li key={index}>{info}</li>
                          ),
                        )}
                      </ul>
                    </div>
                  )}
                </details>
              ))}
            </details>
          </div>}
        </ResearchDialog>
      )}
    </>
  );
}
