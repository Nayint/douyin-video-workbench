import { useDraftState } from "./useDraftState";
import { useState, useEffect, useRef, type ReactNode } from "react";
import {
  ArrowUpRight,
  Film,
  Star,
  X,
  Upload,
  Link2,
  FileText,
  LoaderCircle,
} from "lucide-react";
import { api, media, stamp, type Row } from "./api";
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Film size={28} />
      <p>{children}</p>
    </div>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}
export function CaseCard({
  item,
  onOpen,
  onFavorite,
}: {
  item: Row;
  onOpen: (id: string) => void;
  onFavorite: () => void;
}) {
  return (
    <article data-case-id={item.id} className="case-card" onClick={() => onOpen(item.id)}>
      <button
        className="cover"
        aria-label={"打开素材：" + item.title}
        onClick={(e) => {
          e.stopPropagation();
          onOpen(item.id);
        }}
      >
        {item.cover ? (
          <img src={media(item.cover)} alt={item.title} />
        ) : (
          <div className="cover-placeholder">
            <Film size={32} />
            <span>{item.platform || "本地素材"}</span>
          </div>
        )}
        <span className="duration">
          {item.duration ? Math.round(item.duration) + " 秒" : "手动案例"}
        </span>
      </button>
      <div className="case-body">
        <div className="row">
          <Badge>{item.category || item.platform || "未分类"}</Badge>
          <button
            className={"icon " + (item.favorite ? "active" : "")}
            aria-label={item.favorite ? "取消收藏" : "收藏案例"}
            onClick={(e) => {
              e.stopPropagation();
              api("/cases/" + item.id, "PATCH", {
                favorite: !item.favorite,
              })
                .then(onFavorite)
                .catch(console.error);
            }}
          >
            <Star size={16} fill={item.favorite ? "currentColor" : "none"} />
          </button>
        </div>
        <button
          className="text-button case-title"
          onClick={(e) => {
            e.stopPropagation();
            onOpen(item.id);
          }}
        >
          <span>{item.title}</span>
          <span className="card-open-affordance" aria-hidden="true">
            <ArrowUpRight size={15} />
          </span>
        </button>
        <div className={"case-status " + (item.has_research ? "ready" : "")}>
          <i />
          {item.has_research ? "已有研究结果" : "待研究"}
        </div>
        <div className="muted row">
          <span>{stamp(item.created_at)}</span>
          <span>{item.author || "作者未知"}</span>
        </div>
      </div>
    </article>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const first = dialog.current?.querySelector<HTMLElement>(
      "input, textarea, button, select, a[href]",
    );
    first?.focus();
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
      previous?.focus();
    };
  }, []);
  return (
    <div className="modal-scrim" onClick={onClose}>
      <section
        ref={dialog}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            onClose();
          }
          if (e.key === "Tab") {
            const focusable = dialog.current?.querySelectorAll<HTMLElement>(
              "button:not(:disabled), input, textarea, select, a[href]",
            );
            if (!focusable?.length) return;
            const first = focusable[0],
              last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last.focus();
            }
            if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon" aria-label="关闭" onClick={onClose}>
            <X />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function ImportModal({
  onClose,
  onDone,
  onError,
}: {
  onClose: () => void;
  onDone: (id: string, collectOnly: boolean) => void;
  onError: (s: string) => void;
}) {
  const [mode, setMode] = useDraftState("import.mode", "link"),
    [title, setTitle] = useDraftState("import.title", ""),
    [url, setUrl] = useDraftState("import.url", ""),
    [text, setText] = useDraftState("import.text", ""),
    [file, setFile] = useDraftState<File | null>("import.file", null, false),
    [busy, setBusy] = useState(false);
  async function submit(collectOnly = false) {
    setBusy(true);
    try {
      let r;
      if (mode === "upload") {
        if (!file) throw Error("请选择本地视频");
        const f = new FormData();
        f.append("file", file);
        f.append("title", title);
        f.append("collect_only", String(collectOnly));
        f.append("auto_analyze", String(!collectOnly));
        r = (await api("/cases/upload", "POST", f)).case;
      } else if (mode === "link") {
        r = (
          await api("/cases/link", "POST", {
            title: title || "待研究视频",
            source_url: url,
            platform: "抖音",
            collect_only: collectOnly,
            auto_analyze: !collectOnly,
          })
        ).case;
      } else {
        r = await api("/cases", "POST", {
          title,
          transcript: text,
          platform: "手动",
        });
      }
      if (mode === "manual" && !collectOnly)
        await api("/cases/" + r.id + "/research", "POST", {
          type: "all",
          request_key: crypto.randomUUID(),
        });
      setTitle(""); setUrl(""); setText(""); setFile(null);
      onDone(r.id, collectOnly);
      onClose();
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="导入研究素材" onClose={onClose}>
      <div className="tabs">
        {[
          ["link", Link2, "视频链接"],
          ["upload", Upload, "本地视频"],
          ["manual", FileText, "手动录入"],
        ].map(([v, I, label]: any) => (
          <button
            key={v}
            className={mode === v ? "selected" : ""}
            onClick={() => setMode(v)}
          >
            <I size={16} />
            {label}
          </button>
        ))}
      </div>
      <label>
        案例标题
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="给这次研究起个名字"
        />
      </label>
      {mode === "upload" ? (
        <label className="dropzone">
          <Upload size={30} />
          <strong>{file?.name || "点击选择本地短视频"}</strong>
          <span>MP4 / MOV / WebM / MKV · 默认最大 500 MB</span>
          <input
            aria-label="选择视频文件"
            type="file"
            accept="video/*,.mkv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
      ) : mode === "link" ? (
        <>
          <label>
            抖音链接或分享文字
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="粘贴抖音完整分享文字，或 https://v.douyin.com/…"
            />
          </label>
          <p className="hint">
            复用现有 Dify 使用的本地 BiliNote
            服务获取视频内容和逐字稿；不读取浏览器 Cookie。
          </p>
        </>
      ) : (
        <label>
          原始文案
          <textarea
            rows={9}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="粘贴口播逐字稿，封面和公开指标可稍后补充"
          />
        </label>
      )}
      <div className="modal-actions">
        <button onClick={onClose}>取消</button>
        <button disabled={busy} onClick={() => submit(true)}>
          收录
        </button>
        <button
          className="primary"
          disabled={busy}
          onClick={() => submit(false)}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <ArrowUpRight size={16} />
          )}
          导入并开始研究
        </button>
      </div>
    </Modal>
  );
}
export function JsonView({ value }: { value: any }) {
  if (typeof value === "string" || typeof value === "number")
    return <p>{String(value)}</p>;
  if (Array.isArray(value))
    return (
      <ul>
        {value.map((v, i) => (
          <li key={i}>
            <JsonView value={v} />
          </li>
        ))}
      </ul>
    );
  if (!value) return <span className="muted">未知</span>;
  return (
    <div className="analysis-fields">
      {Object.entries(value).map(([k, v]) => (
        <div key={k}>
          <h3>{k === "conclusion" ? "判断" : k === "evidence" ? "依据" : k}</h3>
          <JsonView value={v} />
        </div>
      ))}
    </div>
  );
}
