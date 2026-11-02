import { useEffect, useState } from "react";
import { api, type Row } from "./api";
export function PipiCreationTask({
  id,
  onNew,
}: {
  id: string;
  onNew: () => void;
}) {
  const [task, setTask] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [body, setBody] = useState(""),
    [retrying, setRetrying] = useState(false);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      let terminal = false;
      try {
        const result = await api<Row>("/tasks/" + encodeURIComponent(id));
        if (!alive) return;
        setTask(result);
        setError("");
        terminal = ["succeeded", "failed", "interrupted"].includes(
          result.status,
        );
      } catch (e) {
        if (alive) setError(String(e).replace(/^Error: /, ""));
      }
      if (alive && !terminal) timer = setTimeout(poll, 2500);
    }
    poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id, retrying]);
  useEffect(() => {
    if (!task?.result?.draft_id) return;
    const controller = new AbortController();
    fetch(
      "/api/drafts/" +
        encodeURIComponent(task.result.draft_id) +
        "/export?format=txt",
      { signal: controller.signal },
    )
      .then((r) => {
        if (!r.ok) throw Error("暂时无法读取成稿，可以在原创文案中查看。");
        return r.text();
      })
      .then(setBody)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [task?.result?.draft_id]);
  async function retry() {
    setRetrying(true);
    setError("");
    try {
      setTask(
        await api<Row>("/tasks/" + encodeURIComponent(id) + "/resume", "POST"),
      );
    } catch (e) {
      setError(String(e).replace(/^Error: /, ""));
    } finally {
      setRetrying(false);
    }
  }
  const failed = task && ["failed", "interrupted"].includes(task.status),
    complete = task?.status === "succeeded";
  return (
    <section className="pipi-creation-task" aria-label="皮皮创作进度">
      <h3>
        {complete
          ? "文案写好了，已保存"
          : failed
            ? "这次生成没有完成"
            : "正在写这条文案"}
      </h3>
      <strong>{task?.payload?.draft_name || "正在读取任务…"}</strong>
      {error && <p role="alert">{error}</p>}
      {complete ? (
        <>
          <p>
            {task.result?.fact_check?.status === "passed"
              ? "已通过现有事实核对流程。"
              : "请打开成稿核对内容。"}
          </p>
          {body ? (
            <div className="pipi-copy-result">{body}</div>
          ) : (
            <p role="status">正在读取成稿…</p>
          )}
          <a className="pipi-link" href="/#/drafts">
            打开原创文案
          </a>
          <button onClick={onNew}>再写一条</button>
        </>
      ) : failed ? (
        <>
          <p role="alert">{task.error || "任务已中断，选好的资料仍保留。"}</p>
          <button onClick={retry} disabled={retrying}>
            {retrying ? "正在重新排队…" : "重新生成并核对"}
          </button>
          <button onClick={onNew}>重新选资料</button>
        </>
      ) : (
        <>
          <p role="status">{task?.stage || "正在确认任务状态…"}</p>
          <progress
            aria-label="文案生成进度"
            max={1}
            value={task?.progress || 0}
          />
          <p className="pipi-hint">
            可以关闭对话，任务会继续；再次进入这里可查看进度。
          </p>
        </>
      )}
    </section>
  );
}
