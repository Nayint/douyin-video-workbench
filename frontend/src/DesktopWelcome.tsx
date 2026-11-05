import { useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, FolderOpen, RefreshCw } from "lucide-react";
import { api } from "./api";
import "./DesktopWelcome.css";

type Status = {
  enabled: boolean; completed: boolean; data_path: string; empty: boolean;
  tools: Record<string, boolean>; ollama: boolean; text_installed: boolean;
  vision_installed: boolean; whisper: boolean; authors: string[];
  host?: "web" | "desktop";
  ai?: { bundled: boolean; running: boolean; managed?: boolean; phase?: string; stage?: string; progress?: number; error?: string };
};

export function DesktopWelcome({ onStart, onSettings }: {
  onStart: (action: "import" | "demo" | "create") => void;
  onSettings: () => void;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showSetup, setShowSetup] = useState(false);
  async function check() {
    setBusy(true); setError("");
    try {
      const result = await api<Status>("/setup/status");
      setStatus(result);
      if (result.enabled && !result.completed) setShowSetup(true);
    } catch (e) { setError(String(e).replace(/^Error: /, "")); }
    finally { setBusy(false); }
  }
  useEffect(() => { void check(); }, []);
  useEffect(() => {
    if (!status?.enabled || !["preparing", "downloading"].includes(status.ai?.phase || "")) return;
    const timer = setTimeout(() => { void check(); }, 2000);
    return () => clearTimeout(timer);
  }, [status]);
  if (!status?.enabled) return null;

  async function start(action: "import" | "demo" | "create" | "settings") {
    setBusy(true); setError("");
    try {
      await api("/setup/complete", "POST", { demo: action === "demo" });
      setShowSetup(false);
      setStatus(s => s ? { ...s, completed: true, empty: action === "demo" ? false : s.empty } : s);
      if (action === "settings") onSettings(); else onStart(action);
    } catch (e) { setError(String(e).replace(/^Error: /, "")); }
    finally { setBusy(false); }
  }

  const checks = [
    [status.tools.ffmpeg && status.tools.ffprobe, "视频导入与关键帧", "随软件提供"],
    [status.text_installed && status.ollama, "文字分析与作者创作", "需要文字模型"],
    [status.vision_installed && status.ollama, "图片与封面研究", "需要视觉模型"],
    [status.whisper, "语音转写", "需要转写模型"],
  ] as const;
  return <section className="desktop-welcome" aria-labelledby="desktop-start-title">
    <div className="desktop-welcome-heading">
      <div><span className="eyebrow">{showSetup ? "欢迎使用 ViralLab" : "开始创作"}</span>
        <h2 id="desktop-start-title">{showSetup ? "从你的第一份素材开始。" : "今天，想先做什么？"}</h2>
        <p>视频、产品资料和文案保存在这台电脑，随时可以接着做。</p></div>
      <button className="small" onClick={() => setShowSetup(!showSetup)} aria-expanded={showSetup}>
        {showSetup ? "收起使用指南" : "使用指南"}
      </button>
    </div>
    {error && <p role="alert" className="alert error">{error}</p>}
    {status.ai?.managed && status.ai.phase !== "ready" && <div role="status">
      <p>{status.ai.error || status.ai.stage}</p>
      <progress value={status.ai.progress || 0} max={1} aria-label="模型准备进度" />
      <p className="hint">首次准备需要下载模型。可以先整理资料；分析与生成会在模型准备后继续。</p>
    </div>}
    <div className="desktop-start-actions" aria-busy={busy}>
      <button className="primary" disabled={busy} onClick={() => void start("import")}>
        导入自己的视频<ArrowUpRight size={17} /></button>
      <button disabled={busy} onClick={() => void start("create")}>为产品写文案</button>
      {showSetup && status.empty && <button disabled={busy} onClick={() => void start("demo")}>
        {busy ? "正在准备…" : "先看看演示资料"}</button>}
    </div>
    {showSetup && <div className="desktop-setup-details">
      <div className="desktop-capabilities" aria-label="本机能力检查">
        {checks.map(([ready, label, hint]) => <div key={label} className="desktop-capability">
          <CheckCircle2 size={17} className={ready ? "ready" : "pending"} />
          <span>{label}</span><small>{ready ? "已准备" : hint}</small>
        </div>)}
      </div>
      <div className="desktop-data-location"><FolderOpen size={17} /><div>
        <strong>你的资料位置</strong><code>{status.data_path}</code>
        <p>{status.host === "desktop" ? "可在顶部资料菜单中选择保存位置或导入备份。" : "资料在本机保存；系统设置可创建并下载备份。更换目录或导入旧备份可交给 Codex 按部署说明处理。"}</p>
      </div></div>
      <p className="desktop-setup-note">{status.ai?.bundled ? "文字、视觉与转写模型已内置。" : "首次运行自动准备本地模型，无需 Dify 或模型密钥。"}演示资料为虚构内容，不代表模型生成效果。</p>
      <div className="desktop-setup-footer">
        <button className="small" disabled={busy} onClick={() => void check()}><RefreshCw size={15} />重新检查</button>
        <button className="small" disabled={busy} onClick={() => void start("settings")}>查看 AI 与资料设置<ArrowUpRight size={15} /></button>
      </div>
    </div>}
  </section>;
}
