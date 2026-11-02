import { useEffect, useState } from "react";
import { api, key, type Row, stamp } from "./api";
import { Empty, JsonView } from "./components";
export function CoverStudio({
  id,
  tasks,
  onError,
  onNotice,
}: {
  id: string;
  tasks: Row[];
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
}) {
  const [products, setProducts] = useState<Row[]>([]),
    [references, setReferences] = useState<Row[]>([]),
    [drafts, setDrafts] = useState<Row[]>([]),
    [draft, setDraft] = useState(""),
    [product, setProduct] = useState(""),
    [reference, setReference] = useState(""),
    [description, setDescription] = useState(""),
    [style, setStyle] = useState(""),
    [rows, setRows] = useState<Row[]>([]),
    [busy, setBusy] = useState(false);
  const signature = tasks
    .filter((t) => t.resource_id === id)
    .map((t) => t.id + t.status)
    .join();
  useEffect(() => {
    Promise.all([
      api<Row[]>("/products"),
      api<Row[]>("/cases"),
      api("/settings"),
      api("/cases/" + id),
      api<Row[]>("/drafts"),
    ])
      .then(([p, c, cfg, item, d]) => {
        setDrafts(d.filter((r: Row) => r.case_id === id));
        setDraft(item.cover_draft_id || "");
        setProducts(p);
        setReferences(c.filter((r: Row) => r.cover));
        setStyle(cfg.cover_style_profile);
        setProduct(item.cover_product_id || "");
        setReference(item.cover_reference_case_id || "");
        setDescription(item.cover_reference_style || "");
      })
      .catch(onError);
  }, [id]);
  useEffect(() => {
    api("/cases/" + id)
      .then((c) => setRows(c.analyses.filter((a: Row) => a.type === "cover")))
      .catch(onError);
  }, [id, signature]);
  async function generate() {
    setBusy(true);
    try {
      await api("/settings", "PUT", { cover_style_profile: style });
      await api("/cases/" + id + "/analyze", "POST", {
        type: "cover",
        request_key: key(),
        material: {
          product_id: product,
          draft_id: draft || null,
          reference_case_id: reference || null,
          reference_style: description,
        },
      });
      onNotice("已启动本地封面提示词生成");
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="creation-grid">
      <section className="panel">
        <h2>封面提示词配置</h2>
        <p className="hint">
          垂直账号固定双主体：本人＋本期产品。所有封面沿用同一配色、字体、排版与光线。未提供产品资料时先生成占位方案，不中断研究。
        </p>
        <label>
          产品资料
          <select value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="">暂不指定，按文案生成产品占位方案</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          使用文案
          <select
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              const d = drafts.find((d) => d.id === e.target.value);
              if (d) setProduct(d.product_id);
            }}
          >
            <option value="">当前案例口播文案</option>
            {drafts.map((d) => (
              <option key={d.id} value={d.id}>
                原创文案 · {stamp(d.created_at)} · {d.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <label>
          参考封面图片（可选）
          <select
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          >
            <option value="">无图片参考，使用样式说明</option>
            {references.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          爆款封面样式说明（可选）
          <textarea
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="填写想借鉴的主体、构图、文字层级；没有参考图时只按说明创作，不声称验证爆款效果。"
          />
        </label>
        <label>
          固定系列风格（全账号共用；双主体构图固定）
          <textarea
            rows={8}
            value={style}
            onChange={(e) => setStyle(e.target.value)}
          />
        </label>
        <p className="hint">
          生成时保存全局风格；每个版本保留风格快照。生成图片时必须附本人照片和产品实拍图，工作台不猜测面貌或产品细节。这里只生成文字提示词。
        </p>
        <button
          className="primary"
          disabled={
            busy ||
            tasks.some(
              (t) =>
                t.resource_id === id &&
                t.kind === "analysis" &&
                t.payload?.type === "cover" &&
                ["running", "queued"].includes(t.status),
            )
          }
          onClick={generate}
        >
          {busy ? "正在提交…" : "生成封面提示词"}
        </button>
      </section>
      <section className="panel">
        <h2>封面提示词与历史版本</h2>
        {!rows.length ? (
          <Empty>
            可直接根据文案生成提示词；有产品资料时会结合真实信息。生成图片时请附本人照片和产品实拍图。
          </Empty>
        ) : (
          rows.map((r) => (
            <details
              key={r.id}
              open={r.id === rows[0].id}
              className="analysis-version"
            >
              <summary>
                {stamp(r.created_at)} ·{" "}
                {r.result["可复制的封面提示词"] ? "封面提示词" : "历史封面分析"}
              </summary>
              <p className="hint">
                {r.model} · {r.prompt_version}
              </p>
              {r.result["可复制的封面提示词"] ? (
                <>
                  <textarea
                    aria-label="完整封面提示词"
                    readOnly
                    rows={18}
                    value={r.result["可复制的封面提示词"]}
                  />
                  <button
                    onClick={() =>
                      navigator.clipboard
                        .writeText(r.result["可复制的封面提示词"])
                        .then(() => onNotice("已复制完整提示词"))
                        .catch(onError)
                    }
                  >
                    复制完整提示词
                  </button>
                  <p className="hint">{r.result["参考来源说明"]}</p>
                  {r.note?.uri && (
                    <a className="note-link" href={r.note.uri}>
                      在 Obsidian 打开封面提示词
                    </a>
                  )}
                  <details>
                    <summary>查看创作依据与固定风格</summary>
                    <JsonView
                      value={Object.fromEntries(
                        Object.entries(r.result).filter(
                          ([k]) => k !== "可复制的封面提示词",
                        ),
                      )}
                    />
                  </details>
                </>
              ) : (
                <JsonView value={r.result} />
              )}
            </details>
          ))
        )}
      </section>
    </div>
  );
}
