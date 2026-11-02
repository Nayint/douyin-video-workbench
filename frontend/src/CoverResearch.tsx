import { useEffect, useState } from "react";
import { api, key, media, stamp, type Row } from "./api";
import { Empty, JsonView } from "./components";
export function CoverResearch({
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
  const [item, setItem] = useState<Row | null>(null),
    [busy, setBusy] = useState(false);
  const signature = tasks
    .filter((t) => t.resource_id === id)
    .map((t) => t.id + t.status)
    .join();
  useEffect(() => {
    api<Row>("/cases/" + id)
      .then(setItem)
      .catch(onError);
  }, [id, signature]);
  const active =
    busy ||
    tasks.some(
      (t) => t.resource_id === id && ["queued", "running"].includes(t.status),
    );
  async function run(analyze: boolean) {
    setBusy(true);
    try {
      await api(
        "/cases/" + id + (analyze ? "/analyze" : "/fetch-cover"),
        "POST",
        { type: "cover_visual", request_key: key() },
      );
      onNotice(
        analyze ? "正在获取封面并进行本地视觉研究" : "正在获取原视频封面",
      );
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  const rows = (item?.analyses || []).filter(
    (a: Row) => a.type === "cover_visual",
  );
  return (
    <div className="cover-research">
      <section className="panel">
        <div className="section-head compact">
          <h2>原视频封面</h2>
          <div className="row gap">
            <button disabled={active} onClick={() => run(false)}>
              {item?.cover ? "重新获取封面" : "获取视频封面"}
            </button>
            <label className="upload-inline">
              上传原封面
              <input
                aria-label="上传原封面"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setBusy(true);
                  try {
                    const form = new FormData();
                    form.append("file", file);
                    const c = await api<Row>(
                      "/cases/" + id + "/cover",
                      "POST",
                      form,
                    );
                    setItem(c);
                    onNotice("已保存上传的封面");
                  } catch (error) {
                    onError(error);
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            </label>
            <button
              className="primary"
              disabled={active}
              onClick={() => run(true)}
            >
              分析封面
            </button>
          </div>
        </div>
        {item?.cover ? (
          <figure className="source-cover">
            <img src={media(item.cover)} alt="原视频封面" />
            <figcaption>
              {item.cover_provenance?.source || "本地封面或视频关键帧"}
              {item.cover_provenance?.collected_at
                ? " · " + stamp(item.cover_provenance.collected_at)
                : ""}
            </figcaption>
          </figure>
        ) : (
          <Empty>点击获取原视频封面，分析时也会自动获取。</Empty>
        )}
      </section>
      <section className="panel">
        <h2>封面研究</h2>
        <p className="hint">
          依据真实封面，简要研究主体、文字、构图与吸引注意的方式；设计特点不代表一定能成为爆款。
        </p>
        {!rows.length ? (
          <Empty>完成分析后，结果显示在这里。</Empty>
        ) : (
          rows.map((a: Row) => (
            <details
              key={a.id}
              className="analysis-version"
              open={a.id === rows[0].id}
            >
              <summary>
                {stamp(a.created_at)} · {a.model}
              </summary>
              <JsonView value={a.result} />
            </details>
          ))
        )}
      </section>
    </div>
  );
}
