import { useEffect, useState } from "react";
import { api } from "./api";

export function DesktopSettings({ onError, onNotice }: {
  onError: (error: unknown) => void; onNotice: (text: string) => void;
}) {
  const [status, setStatus] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [backup, setBackup] = useState<any>(null);
  async function refresh() { setStatus(await api("/setup/status")); }
  useEffect(() => { refresh().catch(onError); }, []);
  useEffect(() => {
    if (!["preparing", "downloading"].includes(status?.ai?.phase)) return;
    const timer = setTimeout(() => { refresh().catch(onError); }, 2000);
    return () => clearTimeout(timer);
  }, [status]);
  async function action(name: "restart" | "backup") {
    setBusy(true);
    try {
      if (name === "restart") {
        await api("/setup/ai/restart", "POST"); await refresh();
        onNotice("正在检查并准备本地模型");
      } else { setBackup(await api("/backups", "POST")); }
    } catch (error) { onError(error); }
    finally { setBusy(false); }
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow">本机运行</div><h1>软件设置</h1>
      <p>本地模型分析与创作，素材和结果保存在自己的资料库。</p></div></div>
    <div className="creation-grid">
      <section className="panel"><h2>本地 AI</h2>
        {!status ? <p role="status">正在检查…</p> : <>
          <p role="status">{status.ai?.stage || (status.ai?.running ? "推理引擎正在运行" : "推理引擎未就绪")}</p>
          {status.ai?.error && <p role="alert">{status.ai.error}</p>}
          {status.ai?.managed && status.ai.phase !== "ready" && <progress value={status.ai.progress || 0} max={1} aria-label="模型准备进度" />}
          <dl><dt>分析文案与写文案</dt><dd>{status.text_model}</dd>
            <dt>图片与封面研究</dt><dd>{status.vision_model}</dd>
            <dt>语音转写</dt><dd>faster-whisper small · {status.whisper ? "已准备" : "未就绪"}</dd></dl>
          <p className="hint">无需 Dify、在线模型账号或 API Key。模型保存在本机，首次运行自动下载；建议使用 16 GB 及以上内存。</p>
          <button disabled={busy} onClick={() => void action("restart")}>{busy ? "正在处理…" : "检查并准备模型"}</button>
        </>}
      </section>
      <section className="panel"><h2>我的资料</h2><p className="preserve">{status?.data_path}</p>
        <p className="hint">可下载备份。更换资料目录、导入原工作台备份请让 Codex 按 docs/QUICKSTART.md 处理，原资料会保留。</p>
        <button disabled={busy} onClick={() => void action("backup")}>创建备份</button>
        {backup && <p role="status"><a className="button" href={backup.url} download>保存备份文件</a></p>}
        <p className="hint">关闭软件后可继续使用；重启后保留资料和未提交文字，选中的附件需要重新选择。</p>
      </section>
    </div>
  </>;
}
