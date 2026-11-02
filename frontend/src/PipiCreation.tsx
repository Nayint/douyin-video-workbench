import { useEffect, useState } from "react";
import { api, media, type Row } from "./api";
import { useDraftState } from "./useDraftState";
import {
  creationPayload,
  emptyCreation,
  type CreationState,
} from "./worldCreationPayload";
import { PipiCreationTask } from "./PipiCreationTask";
import { PipiCreationReview } from "./PipiCreationReview";
export function PipiCreation({
  request,
  onHide,
}: {
  request: string;
  onHide: () => void;
}) {
  const [draft, setDraft] = useDraftState<CreationState>(
    "world.pipi.creation",
    emptyCreation(request),
  );
  const [references, setReferences] = useState<Row[]>([]),
    [products, setProducts] = useState<Row[]>([]),
    [preview, setPreview] = useState<Row | null>(null),
    [learningOptions, setLearningOptions] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    Promise.all([api<Row[]>("/creation/references"), api<Row[]>("/products")])
      .then(([refs, items]) => {
        if (alive) {
          setReferences(refs.filter((r) => r.has_structure));
          setProducts(items);
        }
      })
      .catch((e) => {
        if (alive) setError(String(e).replace(/^Error: /, ""));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [attempt]);
  const selectedCase = references.find((r) => r.id === draft.caseId),
    selectedProduct = products.find((p) => p.id === draft.productId);
  function update(changes: Partial<CreationState>) {
    if (
      changes.caseId !== undefined ||
      changes.productId !== undefined ||
      changes.writingMode !== undefined
    )
      setLearningOptions([]);
    setDraft((old) => ({
      ...old,
      ...changes,
      requestKey: crypto.randomUUID(),
    }));
    setPreview(null);
    setError("");
  }
  function back(phase: CreationState["phase"]) {
    setDraft((old) => ({ ...old, phase }));
    setPreview(null);
    setError("");
  }
  async function inspect(learningIds = draft.learningIds) {
    setBusy(true);
    setError("");
    try {
      const result = await api<Row>(
        "/dify/preview",
        "POST",
        creationPayload({ ...draft, learningIds }),
      );
      setPreview(result);
      setLearningOptions((old) =>
        learningIds === null
          ? result.learning_entries || []
          : [
              ...new Map(
                [...old, ...(result.learning_entries || [])].map((e) => [
                  e.id,
                  e,
                ]),
              ).values(),
            ],
      );
      setDraft((old) => ({
        ...old,
        learningIds,
        phase: "preview",
        requestKey:
          JSON.stringify(old.learningIds) === JSON.stringify(learningIds)
            ? old.requestKey
            : crypto.randomUUID(),
      }));
    } catch (e) {
      setPreview(null);
      setError(String(e).replace(/^Error: /, ""));
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    if (!preview || busy || draft.taskId) return;
    setBusy(true);
    setError("");
    try {
      const task = await api<Row>("/dify/generate", "POST", {
        ...creationPayload(draft),
        expected_models: preview.model_selection,
        expected_input_hash: preview.grounding?.hash,
      });
      setDraft((old) => ({ ...old, taskId: task.id }));
    } catch (e) {
      setError(String(e).replace(/^Error: /, ""));
    } finally {
      setBusy(false);
    }
  }
  const phase = draft.phase === "preview" && !preview ? "details" : draft.phase;
  return (
    <section className="pipi-creation" aria-label="和皮皮一起写文案">
      <div className="pipi-creation-heading">
        <h3>一起写条文案</h3>
        <button onClick={onHide}>收起创作</button>
      </div>
      {draft.taskId ? (
        <PipiCreationTask
          id={draft.taskId}
          onNew={() => {
            setDraft(emptyCreation());
            setPreview(null);
            setError("");
          }}
        />
      ) : (
        <>
          <ol className="pipi-steps" aria-label="创作步骤">
            <li aria-current={phase === "case" ? "step" : undefined}>选案例</li>
            <li aria-current={phase === "product" ? "step" : undefined}>
              选产品
            </li>
            <li
              aria-current={
                phase === "details" || phase === "preview" ? "step" : undefined
              }
            >
              核对并生成
            </li>
          </ol>
          {(draft.caseId || draft.productId) && (
            <div className="pipi-selections">
              {draft.caseId && (
                <button onClick={() => back("case")} disabled={busy}>
                  案例：{selectedCase?.title || "已选案例暂不可用"} · 更换
                </button>
              )}
              {draft.productId && (
                <button onClick={() => back("product")} disabled={busy}>
                  产品：{selectedProduct?.name || "已选产品暂不可用"} · 更换
                </button>
              )}
            </div>
          )}
          {loading ? (
            <p role="status">正在读取研究案例和产品资料…</p>
          ) : error && (!references.length || !products.length) ? (
            <>
              <p role="alert">{error}</p>
              <button onClick={() => setAttempt((n) => n + 1)}>
                重新读取资料
              </button>
            </>
          ) : (
            <>
              {error && <p role="alert">{error}</p>}
              {phase === "case" && (
                <>
                  <h4>先选一个参考案例</h4>
                  <p className="pipi-hint">
                    只参考叙事顺序，措辞和口吻使用皮皮的作者卡。
                  </p>
                  {!references.length ? (
                    <p>
                      还没有完成视频架构分析的案例。
                      <a href="/#/library">前往研究所</a>
                    </p>
                  ) : (
                    <div className="pipi-choices">
                      {references.map((r) => (
                        <button
                          key={r.id}
                          aria-pressed={draft.caseId === r.id}
                          onClick={() =>
                            update({
                              caseId: r.id,
                              phase: "product",
                              learningIds: null,
                            })
                          }
                        >
                          {r.cover && <img src={media(r.cover)} alt="" />}
                          <span>
                            <strong>{r.title}</strong>
                            <small>已完成视频架构分析</small>
                          </span>
                          <span aria-hidden="true">→</span>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
              {phase === "product" && (
                <>
                  <h4>接下来，选这次要写的产品</h4>
                  {!products.length ? (
                    <p>
                      产品库里还没有资料。<a href="/#/products">前往产品库</a>
                    </p>
                  ) : (
                    <div className="pipi-choices">
                      {products.map((p) => (
                        <button
                          key={p.id}
                          aria-pressed={draft.productId === p.id}
                          onClick={() =>
                            update({
                              productId: p.id,
                              phase: "details",
                              learningIds: null,
                            })
                          }
                        >
                          <span>
                            <strong>{p.name}</strong>
                            <small>使用产品库中的真实资料</small>
                          </span>
                          <span aria-hidden="true">→</span>
                        </button>
                      ))}
                    </div>
                  )}
                  <button onClick={() => back("case")}>返回选案例</button>
                </>
              )}
              {phase === "details" && (
                <form
                  className="pipi-details"
                  onSubmit={(e) => {
                    e.preventDefault();
                    inspect();
                  }}
                >
                  <h4>还有这些想法，可以告诉我</h4>
                  <label>
                    文案名称
                    <input
                      required
                      maxLength={200}
                      value={draft.draftName}
                      onChange={(e) => update({ draftName: e.target.value })}
                      placeholder="给这条文案起个名字"
                      disabled={busy}
                    />
                  </label>
                  <label>
                    写作方式
                    <select
                      value={draft.writingMode}
                      onChange={(e) =>
                        update({
                          writingMode: e.target.value,
                          learningIds: null,
                        })
                      }
                      disabled={busy}
                    >
                      {["生活分享", "直接推荐", "演示答疑"].map((mode) => (
                        <option key={mode}>{mode}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    本次文案要求（选填）
                    <textarea
                      rows={3}
                      maxLength={3500}
                      value={draft.requirements}
                      onChange={(e) => update({ requirements: e.target.value })}
                      placeholder="时长、受众、口吻、重点或禁用词"
                      disabled={busy}
                    />
                  </label>
                  <label>
                    个人真实体验（选填）
                    <textarea
                      rows={2}
                      maxLength={3000}
                      value={draft.experience}
                      onChange={(e) => update({ experience: e.target.value })}
                      placeholder="没有亲测可以留空"
                      disabled={busy}
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={
                      busy ||
                      !draft.draftName.trim() ||
                      !selectedCase ||
                      !selectedProduct
                    }
                  >
                    {busy ? "正在核对资料…" : "核对这次创作资料"}
                  </button>
                </form>
              )}
              {phase === "preview" && preview && (
                <>
                  <PipiCreationReview
                    preview={preview}
                    options={learningOptions}
                    selected={
                      draft.learningIds ??
                      (preview.learning_entries || []).map((e: Row) => e.id)
                    }
                    name={draft.draftName}
                    busy={busy}
                    onLearning={(ids) => inspect(ids)}
                  />
                  <div className="pipi-submit">
                    <button disabled={busy} onClick={() => back("details")}>
                      返回修改
                    </button>
                    <button disabled={busy} onClick={() => inspect()}>
                      重新核对
                    </button>
                    <button disabled={busy} onClick={generate}>
                      {busy ? "正在处理…" : "确认资料，开始生成"}
                    </button>
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
