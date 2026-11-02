import type { Row } from "./api";
export function PipiCreationReview({
  preview,
  name,
  onLearning,
  options,
  selected,
  busy,
}: {
  preview: Row;
  name: string;
  onLearning: (ids: string[] | null) => void;
  options: Row[];
  selected: string[];
  busy: boolean;
}) {
  const entries = options;
  return (
    <section className="pipi-review" aria-label="本次创作资料核对">
      <h3>最后看一下，这次这样写</h3>
      <strong>{name}</strong>
      <dl>
        <dt>表达风格</dt>
        <dd>
          {preview.author?.name} ·{" "}
          {preview.grounding?.context?.writing_mode || ""}
        </dd>
        <dt>参考架构</dt>
        <dd>
          {preview.structure_reference?.title}
          <p>{preview.structure_reference?.steps?.join(" → ")}</p>
        </dd>
        <dt>生成文案的模型</dt>
        <dd>{preview.model_selection?.text_model}</dd>
      </dl>
      <details open>
        <summary>本次产品资料</summary>
        <p className="pipi-facts">{preview.grounding?.product_facts}</p>
      </details>
      <p className="pipi-hint">
        只借案例的顺序和节奏，商品事实以这里为准。真实体验未填写时，不代写亲测经历。
      </p>
      {!!entries.length && (
        <details>
          <summary>本次采用的写作经验（{entries.length}）</summary>
          {entries.map((entry) => (
            <label className="pipi-learning" key={entry.id}>
              <input
                type="checkbox"
                checked={selected.includes(entry.id)}
                disabled={busy}
                onChange={() =>
                  onLearning(
                    selected.includes(entry.id)
                      ? selected.filter((id) => id !== entry.id)
                      : [...selected, entry.id],
                  )
                }
              />
              <span>
                {entry.title}
                <small>{entry.reason || entry.quote?.slice(0, 100)}</small>
              </span>
            </label>
          ))}
          <p className="pipi-hint">勾选变化会重新核对本次资料。</p>
          <button disabled={busy} onClick={() => onLearning(null)}>
            恢复默认匹配
          </button>
        </details>
      )}
    </section>
  );
}
