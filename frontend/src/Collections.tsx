import { WritingAnnotations, LearningShelf } from "./WritingLearning";
import { useDraftState } from "./useDraftState";
import { ResearchProgress } from "./ResearchProgress";
import { useState, useEffect, useRef, type CSSProperties } from "react";
import { api, key, stamp, clean, type Row } from "./api";
import { CaseCard, Empty, Modal, JsonView } from "./components";
import {
  LayoutGrid,
  List,
  MoreHorizontal,
  RefreshCw,
  Trash2,
  FileText,
  CheckCircle2,
} from "lucide-react";

export function Collection({
  cases,
  onOpen,
  onRefresh,
  onError,
  onNotice,
  onSelection,
}: {
  cases: Row[];
  onOpen: (id: string) => void;
  onRefresh: () => void;
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
  onSelection?: (ids: string[]) => void;
}) {
  const [view, setView] = useState(() => {
    try {
      const v = JSON.parse(localStorage.getItem("asset-view-v2") || "{}");
      return {
        size: ["170", "215", "285"].includes(v.size) ? v.size : "215",
        ratio: ["1", "16 / 9", "9 / 16"].includes(v.ratio) ? v.ratio : "1",
        info: v.info !== false,
        layout: v.layout === "text" ? "text" : "cards",
      };
    } catch {
      return { size: "215", ratio: "1", info: true, layout: "cards" };
    }
  });
  const layout = view.layout;
  const setLayout = (layout: string) => setView({ ...view, layout });
  useEffect(() => {
    localStorage.setItem("asset-view-v2", JSON.stringify(view));
  }, [view]);
  const [selected, setSelected] = useState<string[]>([]),
    [removed, setRemoved] = useState<string[]>([]),
    [context, setContext] = useState<{
      x: number;
      y: number;
      ids: string[];
    } | null>(null),
    [deleting, setDeleting] = useState<string[] | null>(null),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const close = () => setContext(null);
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("keydown", escape);
    };
  }, []);
  useEffect(() => {
    onSelection?.(selected);
  }, [selected]);
  const caseIds = cases.map((c) => c.id).join(",");
  useEffect(
    () =>
      setSelected((old) => old.filter((id) => cases.some((c) => c.id === id))),
    [caseIds],
  );
  const allSelected =
    cases.length > 0 && cases.every((c) => selected.includes(c.id));
  const choose = (id: string) =>
    setSelected((v) =>
      v.includes(id) ? v.filter((x) => x !== id) : [...v, id],
    );
  async function analyze(ids: string[]) {
    setBusy(true);
    try {
      for (const id of ids)
        await api("/cases/" + id + "/research", "POST", {
          type: "all",
          request_key: key(),
        });
      onNotice("已加入文案、标题、封面三项研究队列");
      onRefresh();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
      setContext(null);
    }
  }
  function menu(e: React.MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    setContext({
      x: Math.min(e.clientX, window.innerWidth - 190),
      y: Math.min(e.clientY, window.innerHeight - 120),
      ids: selected.includes(id) ? selected : [id],
    });
  }
  return (
    <>
      {removed.length > 0 && (
        <div className="alert success">
          已删除 {removed.length} 条素材。
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                for (const id of removed)
                  await api("/cases/" + id + "/restore", "POST");
                setRemoved([]);
                onRefresh();
                onNotice("已恢复删除的素材");
              } catch (e) {
                onError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            撤销删除
          </button>
        </div>
      )}
      <div className="collection-toolbar">
        <div className="row gap">
          <label className="selection-all">
            <input
              type="checkbox"
              aria-label="选择当前全部素材"
              checked={allSelected}
              ref={(e) => {
                if (e) e.indeterminate = selected.length > 0 && !allSelected;
              }}
              onChange={() =>
                setSelected(allSelected ? [] : cases.map((c) => c.id))
              }
            />
            全选
          </label>
          <strong>{cases.length} 条素材</strong>
          <span className="muted">已选 {selected.length} 条</span>
          {selected.length > 0 && (
            <>
              <button disabled={busy} onClick={() => analyze(selected)}>
                分析所选
              </button>
              <button onClick={() => setDeleting(selected)}>删除所选</button>
            </>
          )}
        </div>
        <div className="row gap">
          <details
            className="view-options"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.currentTarget.open = false;
                e.currentTarget.querySelector("summary")?.focus();
              }
            }}
          >
            <summary>外观</summary>
            <div className="view-options-panel">
              <label>
                卡片大小
                <select
                  aria-label="卡片大小"
                  value={view.size}
                  onChange={(e) => setView({ ...view, size: e.target.value })}
                >
                  <option value="170">小</option>
                  <option value="215">中</option>
                  <option value="285">大</option>
                </select>
              </label>
              <label>
                缩略图比例
                <select
                  aria-label="缩略图比例"
                  value={view.ratio}
                  onChange={(e) => setView({ ...view, ratio: e.target.value })}
                >
                  <option value="1">1:1</option>
                  <option value="16 / 9">16:9</option>
                  <option value="9 / 16">9:16</option>
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={view.info}
                  onChange={(e) => setView({ ...view, info: e.target.checked })}
                />
                显示卡片信息
              </label>
            </div>
          </details>
          <div className="tabs view-switch" aria-label="展示方式">
            <button
              className={layout === "cards" ? "selected" : ""}
              onClick={() => setLayout("cards")}
            >
              <LayoutGrid size={16} />
              卡片模式
            </button>
            <button
              className={layout === "text" ? "selected" : ""}
              onClick={() => setLayout("text")}
            >
              <List size={16} />
              文本模式
            </button>
          </div>
        </div>
      </div>
      {!cases.length ? (
        <Empty>还没有素材，请导入链接、视频或手动文案后收录。</Empty>
      ) : layout === "cards" ? (
        <div
          className={"case-grid " + (!view.info ? "hide-card-info" : "")}
          style={
            {
              "--asset-size": view.size + "px",
              "--asset-ratio": view.ratio,
            } as CSSProperties
          }
        >
          {cases.map((c) => (
            <div
              key={c.id}
              className={
                selected.includes(c.id)
                  ? "collection-item is-selected"
                  : "collection-item"
              }
              onContextMenu={(e) => menu(e, c.id)}
            >
              <CaseCard item={c} onOpen={onOpen} onFavorite={onRefresh} />
              <div className="row collection-select">
                <label>
                  <input
                    type="checkbox"
                    checked={selected.includes(c.id)}
                    onChange={() => choose(c.id)}
                    aria-label={"选择" + c.title}
                  />
                  选择
                </label>
                <button
                  className="icon"
                  aria-label={"操作" + c.title}
                  onClick={(e) => menu(e, c.id)}
                >
                  <MoreHorizontal size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="panel collected-list">
          {cases.map((c) => (
            <div
              key={c.id}
              className="collected-row"
              data-case-id={c.id}
              onContextMenu={(e) => menu(e, c.id)}
            >
              <input
                type="checkbox"
                aria-label={"选择" + c.title}
                checked={selected.includes(c.id)}
                onChange={() => choose(c.id)}
              />
              <button
                className="text-button collected-title"
                onClick={() => onOpen(c.id)}
              >
                <strong>{c.title}</strong>
                <span>
                  {c.platform} · {stamp(c.created_at)}
                </span>
              </button>
              <button
                className="icon"
                aria-label={"操作" + c.title}
                onClick={(e) => menu(e, c.id)}
              >
                <MoreHorizontal size={18} />
              </button>
            </div>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <div className="selection-bar" role="region" aria-label="素材批量操作">
          <strong>已选择 {selected.length} 项素材</strong>
          <button onClick={() => setSelected([])}>清除选择</button>
          <button
            className="primary"
            disabled={busy}
            onClick={() => analyze(selected)}
          >
            分析所选
          </button>
          <button disabled={busy} onClick={() => setDeleting(selected)}>
            删除所选
          </button>
        </div>
      )}
      {context && (
        <div
          className="context-menu"
          role="menu"
          style={{ left: context.x, top: context.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            role="menuitem"
            disabled={busy}
            onClick={() => analyze(context.ids)}
          >
            <RefreshCw size={16} />
            分析 {context.ids.length > 1 ? context.ids.length + " 条" : ""}
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setDeleting(context.ids);
              setContext(null);
            }}
          >
            <Trash2 size={16} />
            删除
          </button>
        </div>
      )}
      {deleting && (
        <Modal title="删除收录素材" onClose={() => setDeleting(null)}>
          <p>
            将从工作台移除 {deleting.length} 条素材。原始文件、Obsidian
            笔记和已有文案保留。
          </p>
          <div className="modal-actions">
            <button onClick={() => setDeleting(null)}>取消</button>
            <button
              className="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  for (const id of deleting)
                    await api("/cases/" + id, "DELETE");
                  setRemoved(deleting);
                  setSelected([]);
                  setDeleting(null);
                  onNotice("已移除所选素材");
                } catch (e) {
                  onError(e);
                } finally {
                  setBusy(false);
                  onRefresh();
                }
              }}
            >
              确认删除
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function TaskCenter({
  tasks,
  cases,
  onOpen,
  onRefresh,
  onError,
}: {
  tasks: Row[];
  cases: Row[];
  onOpen: (id: string) => void;
  onRefresh: () => void;
  onError: (e: unknown) => void;
}) {
  const [deletedTask, setDeletedTask] = useState<Row | null>(null);
  const [deleting, setDeleting] = useState<string[]>([]);
  const [restoring, setRestoring] = useState(false);
  async function deleteTask(task: Row) {
    setDeleting((ids) => [...ids, task.id]);
    try {
      await api('/tasks/' + task.id, 'DELETE');
      setDeletedTask(task);
      onRefresh();
    } catch (e) {
      onError(e);
    } finally {
      setDeleting((ids) => ids.filter((id) => id !== task.id));
    }
  }
  const rows = tasks.filter((t) =>
    ["failed", "interrupted", "queued", "running"].includes(t.status),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">TASK CENTER</div>
          <h1>待处理任务</h1>
          <p>查看未完成的研究、失败原因，并继续重试。</p>
        </div>
      </div>
      {deletedTask && (
        <div className="panel row gap" role="status">
          <span>
            任务卡片已删除，关联素材和结果保留。
            {["queued", "running"].includes(deletedTask.status) && "任务仍会继续执行。"}
          </span>
          <button disabled={restoring} onClick={async () => {
            setRestoring(true);
            try {
              await api('/tasks/' + deletedTask.id + '/restore', 'POST');
              setDeletedTask(null);
              onRefresh();
            } catch (e) { onError(e); }
            finally { setRestoring(false); }
          }}>{restoring ? '正在恢复…' : '撤销删除'}</button>
        </div>
      )}
      {!rows.length ? (
        <Empty>目前没有待处理或失败任务。</Empty>
      ) : (
        rows.map((t) => (
          <section className="panel pending-task" key={t.id}>
            <div className="row gap">
              <button
                className="text-button"
                onClick={() => t.resource_id && onOpen(t.resource_id)}
              >
                <strong>
                  {cases.find((c) => c.id === t.resource_id)?.title ||
                    "独立研究任务"}
                </strong>
              </button>
              <span className="badge">
                {
                  {
                    failed: "失败",
                    interrupted: "已中断",
                    queued: "排队中",
                    running: "处理中",
                  }[t.status as string]
                }
              </span>
              <button
                className="text-button"
                aria-label={"删除任务 " + (cases.find((c) => c.id === t.resource_id)?.title || t.stage)}
                title="移除任务卡片；保留素材和结果，正在执行的任务继续运行"
                disabled={deleting.includes(t.id)}
                onClick={() => deleteTask(t)}
              >
                <Trash2 size={15} />
                {deleting.includes(t.id) ? "正在删除…" : "删除"}
              </button>
            </div>
            <p>{t.stage}</p>
            <ResearchProgress task={t} />
            {t.result?.completed?.length > 0 && (
              <p className="muted">
                已完成：
                {t.result.completed
                  .map(
                    (v: string) =>
                      ({
                        video: "文案研究",
                        title: "标题研究",
                        cover: "封面提示词",
                        cover_visual: "封面研究",
                      })[v],
                  )
                  .join("、")}
              </p>
            )}
            {t.error && <p className="task-error">{t.error}</p>}
            {["failed", "interrupted"].includes(t.status) ? (
              <button
                onClick={() =>
                  api("/tasks/" + t.id + "/resume", "POST")
                    .then(onRefresh)
                    .catch(onError)
                }
              >
                <RefreshCw size={15} />
                重试
              </button>
            ) : (
              <progress max={1} value={t.progress} />
            )}
          </section>
        ))
      )}
    </>
  );
}
export function Drafts({
  onError,
  onNotice,
}: {
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
}) {
  const [annotating, setAnnotating] = useDraftState<Row | null>("drafts.annotating", null, false);
  const [showLearning, setShowLearning] = useState(false);
  const [rows, setRows] = useState<Row[]>([]),
    [editing, setEditing] = useDraftState<Row | null>("drafts.editing", null, false),
    [text, setText] = useDraftState("drafts.text", ""),
    [savingStatus, setSavingStatus] = useState<string[]>([]),
    [context, setContext] = useState<{ id: string; x: number; y: number } | null>(null),
    [removed, setRemoved] = useState<Row | null>(null),
    [deleting, setDeleting] = useState(false);
  const contextTrigger = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!context) return;
    const close = () => setContext(null);
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close();
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
  const load = () => api<Row[]>("/drafts").then(setRows).catch(onError);
  useEffect(() => {
    load();
  }, []);
  function openContext(id: string, x: number, y: number, target: HTMLElement) {
    contextTrigger.current = target;
    setContext({ id, x: Math.max(8, Math.min(x, window.innerWidth - 208)),
      y: Math.max(8, Math.min(y, window.innerHeight - 64)) });
  }
  async function remove(id: string) {
    setContext(null);
    setDeleting(true);
    try {
      const draft = rows.find(d => d.id === id);
      await api("/drafts/" + id, "DELETE");
      setRows(old => old.filter(d => d.id !== id));
      if (editing?.id === id) setEditing(null);
      if (draft) setRemoved(draft);
    } catch (e) { onError(e); }
    finally { setDeleting(false); }
  }
  async function undoRemove() {
    if (!removed) return;
    setDeleting(true);
    try {
      await api("/drafts/" + removed.id + "/restore", "POST");
      await load();
      setRemoved(null);
      onNotice("文案已恢复");
    } catch (e) { onError(e); }
    finally { setDeleting(false); }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ORIGINAL SCRIPTS</div>
          <h1>原创文案</h1>
          <p>管理待拍摄与已完成的文案，每个创作版本都保留下来。</p>
          <button onClick={()=>setShowLearning(!showLearning)}>{showLearning?"收起沉淀库":"查看文案沉淀库"}</button>
        </div>
      </div>
      {showLearning && <LearningShelf onError={onError}/>}
      {removed && <div className="panel row gap product-delete-notice" role="status">
        <span>已删除“{removed.title || "口播文案"}”，原稿和关联资料保留。</span>
        <button disabled={deleting} onClick={undoRemove}>撤销删除</button>
      </div>}
      {!rows.length ? (
        <Empty>还没有原创文案，可从研究所选择案例开始创作。</Empty>
      ) : (
        <div className="draft-grid">
          {rows.map((d) => (
            <article className={"panel draft-card" + (d.filmed ? " draft-card-filmed" : "")} key={d.id}
              tabIndex={0} aria-label={"文案：" + (d.title || d.id.slice(0, 8))}
              onContextMenu={e => {
                e.preventDefault(); e.stopPropagation();
                openContext(d.id, e.clientX, e.clientY, e.currentTarget);
              }}
              onKeyDown={e => {
                if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
                  e.preventDefault();
                  const rect = e.currentTarget.getBoundingClientRect();
                  openContext(d.id, rect.left + 16, rect.top + 40, e.currentTarget);
                }
              }}>
              <div className="row">
                <strong>
                  <FileText size={16} />
                  {d.title || "口播文案 · " + d.id.slice(0, 8)}
                </strong>
                <span className={"badge draft-filming-badge" + (d.filmed ? " filmed" : "")}>
                  {d.filmed && <CheckCircle2 size={15} aria-hidden="true" />}
                  {d.filmed ? "已拍摄" : "待拍摄"}
                </span>
              </div>
              <p className="muted">
                {stamp(d.created_at)} ·{" "}
                {d.revision_type === "layout" ? "排版修订版本" : d.parent_id ? "人工修改版本" : "生成版本"}
              </p>
              {!!d.generation_models?.length && (
                <p className="hint">实际调用模型：{[...new Set(d.generation_models.map((m: any) => m.model))].join("、")}</p>
              )}
              <div className="draft-content">{clean(d.content).replace(/ +$/gm, "")}</div>
              <button onClick={()=>setAnnotating(d)}>逐段标注</button>
              <div className="row gap">
                <button
                  aria-pressed={!!d.filmed}
                  disabled={savingStatus.includes(d.id)}
                  onClick={async () => {
                    setSavingStatus((ids) => [...ids, d.id]);
                    try {
                      const updated = await api<Row>("/drafts/" + d.id + "/filming", "PATCH", { filmed: !d.filmed });
                      setRows((current) => current.map((row) => row.id === d.id ? { ...row, ...updated } : row));
                      onNotice(updated.filmed ? "已标记为已拍摄" : "已改为待拍摄");
                    } catch (e) {
                      onError(e);
                    } finally {
                      setSavingStatus((ids) => ids.filter((id) => id !== d.id));
                    }
                  }}
                >
                  {savingStatus.includes(d.id) ? "保存中…" : d.filmed ? "改为待拍摄" : "标记已拍摄"}
                </button>
                <button
                  onClick={() => {
                    setEditing(d);
                    setText(clean(d.content).replace(/ +$/gm, ""));
                  }}
                >
                  编辑新版本
                </button>
                <a
                  className="button"
                  href={"/api/drafts/" + d.id + "/export?format=txt"}
                >
                  导出 TXT
                </a>
                {d.note?.uri && (
                  <a className="text-button" href={d.note.uri}>
                    Obsidian 笔记
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {context && <div className="context-menu" role="menu" aria-label="文案操作"
        style={{ left: context.x, top: context.y }} onClick={e => e.stopPropagation()}>
        <button role="menuitem" autoFocus disabled={deleting || savingStatus.includes(context.id)} onClick={() => remove(context.id)}>
          <Trash2 size={16} />删除
        </button>
      </div>}
      {annotating && <Modal title={"标注："+annotating.title} onClose={()=>setAnnotating(null)}><WritingAnnotations key={annotating.id} draft={annotating} onError={onError} onNotice={onNotice}/></Modal>}
      {editing && (
        <Modal title="编辑原创文案" onClose={() => setEditing(null)}>
          <textarea
            aria-label="原创文案正文"
            rows={16}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="modal-actions">
            <button
              className="primary"
              onClick={async () => {
                try {
                  await api("/drafts/" + editing.id + "/versions", "POST", {
                    content: text,
                  });
                  setEditing(null);
                  load();
                  onNotice("已保存新版本，原文保留");
                } catch (e) {
                  onError(e);
                }
              }}
            >
              保存新版本
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function ComparisonReports({ tasks }: { tasks: Row[] }) {
  const [rows, setRows] = useState<Row[]>([]);
  const signature = tasks.map((t) => t.id + t.status).join();
  useEffect(() => {
    api<Row[]>("/analyses")
      .then((r) => setRows(r.filter((a) => a.type === "compare")))
      .catch(() => {});
  }, [signature]);
  if (!rows.length) return null;
  return (
    <section className="panel comparison-reports">
      <h2>案例对比报告</h2>
      {rows.map((r) => (
        <details key={r.id}>
          <summary>
            {stamp(r.created_at)} · {r.model}
          </summary>
          <JsonView value={r.result} />
        </details>
      ))}
    </section>
  );
}
