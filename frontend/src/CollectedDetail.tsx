import { useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";
import { api, key, type Row } from "./api";
import { VideoOverview } from "./VideoOverview";
import { Empty, Modal, Badge } from "./components";

export function CollectedDetail({
  id,
  onBack,
  onRefresh,
  onError,
  onNotice,
  tasks,
  onResearch,
}: {
  id: string;
  onBack: () => void;
  onRefresh: () => void;
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
  tasks: Row[];
  onResearch: () => void;
}) {
  const [item, setItem] = useState<Row | null>(null),
    [title, setTitle] = useState(""),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [deleted, setDeleted] = useState(false);
  useEffect(() => {
    setItem(null);
    setDeleted(false);
    api<Row>("/cases/" + id)
      .then((c) => {
        setItem(c);
        setTitle(c.title);
      })
      .catch(onError);
  }, [id]);
  const taskSignature = tasks
    .filter((t) => t.resource_id === id)
    .map((t) => t.id + t.status)
    .join();
  useEffect(() => {
    if (
      tasks.some(
        (t) =>
          t.resource_id === id && ["succeeded", "failed"].includes(t.status),
      )
    )
      api<Row>("/cases/" + id)
        .then((r) => {
          setItem(r);
        })
        .catch(onError);
  }, [taskSignature, id]);
  async function save() {
    setBusy(true);
    try {
      const changes: Record<string, string> = { title };
      const r = await api<Row>("/cases/" + id, "PATCH", changes);
      setItem(r);
      onRefresh();
      await api("/cases/" + id + "/research", "POST", {
        type: "all",
        request_key: key(),
      });
      onRefresh();
      onNotice("已保存标题并启动文案、标题、封面三项研究，完成后进入研究所");
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  if (deleted)
    return (
      <section className="panel">
        <h1>已删除收录素材</h1>
        <p>原始文件和 Obsidian 笔记保留，可撤销本次删除。</p>
        <div className="row gap">
          <button onClick={onBack}>返回已收录视频</button>
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api("/cases/" + id + "/restore", "POST");
                setDeleted(false);
                onRefresh();
                onNotice("已恢复收录素材");
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
      </section>
    );
  if (!item) return <Empty>正在读取收录详情…</Empty>;
  return (
    <>
      <button className="text-button back" onClick={onBack}>
        <ArrowLeft size={16} />
        返回已收录视频
      </button>
      <div className="page-heading">
        <div>
          <div className="eyebrow">COLLECTED MATERIAL</div>
          <h1>收录详情</h1>
          <p>
            查看收录时保存的信息，确认标题后点击“分析”，保存修改并开始三项研究。
          </p>
        </div>
        <Badge>收录素材</Badge>
      </div>
      {tasks
        .filter((t) => t.resource_id === id)
        .slice(0, 1)
        .map((t) => (
          <div
            className={"task-banner " + (t.status === "failed" ? "failed" : "")}
            key={t.id}
          >
            <span>{t.stage}</span>
            <span>{t.error || Math.round(t.progress * 100) + "%"}</span>
          </div>
        ))}
      {item.analyses?.length > 0 && (
        <div className="alert success">
          已生成研究结果，未完成项可在任务中心重试。
          <button onClick={onResearch}>查看研究结果</button>
        </div>
      )}
      <VideoOverview
        item={item}
        tasks={tasks}
        onError={onError}
        onNotice={onNotice}
        headerControl={
          <label>
            项目名称（仅作管理命名）
            <input
              aria-label="项目名称"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
            />
          </label>
        }
      />
      <div className="collected-detail-actions">
        <button onClick={() => setConfirm(true)} disabled={busy}>
          <Trash2 size={16} />
          删除
        </button>
        <button
          className="primary"
          disabled={
            busy ||
            !title.trim() ||
            tasks.some(
              (t) =>
                t.resource_id === id &&
                ["running", "queued"].includes(t.status),
            )
          }
          onClick={save}
        >
          <RefreshCw size={16} />
          {busy ? "正在启动…" : "分析"}
        </button>
      </div>
      {confirm && (
        <Modal title="删除收录素材" onClose={() => setConfirm(false)}>
          <p>确认删除“{item.title}”？原始文件和 Obsidian 笔记保留。</p>
          <div className="modal-actions">
            <button onClick={() => setConfirm(false)}>取消</button>
            <button
              className="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api("/cases/" + id, "DELETE");
                  setConfirm(false);
                  setDeleted(true);
                  onRefresh();
                  onNotice("已删除收录素材，可在当前页面撤销");
                } catch (e) {
                  onError(e);
                } finally {
                  setBusy(false);
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
