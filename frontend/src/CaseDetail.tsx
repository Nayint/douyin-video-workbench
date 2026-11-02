import { ResearchProgress } from "./ResearchProgress";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Play,
  Save,
  RefreshCw,
  Upload,
  FileText,
  ExternalLink,
  PenLine,
  Clock,
  ChevronRight,
} from "lucide-react";
import { VideoOverview } from "./VideoOverview";
import { CoverResearch } from "./CoverResearch";
import { transcriptParagraphs } from "./transcript";
import { api, media, stamp, key, type Row } from "./api";
import { Badge, Empty, JsonView, Modal } from "./components";
type Props = {
  id: string;
  tasks: Row[];
  onBack: () => void;
  onError: (e: unknown) => void;
  onNotice: (s: string) => void;
  onCreate: () => void;
};
export function CaseDetail({
  id,
  tasks,
  onBack,
  onError,
  onNotice,
  onCreate,
}: Props) {
  const [item, setItem] = useState<any>(null),
    [text, setText] = useState(""),
    [notes, setNotes] = useState(""),
    [tags, setTags] = useState(""),
    [category, setCategory] = useState(""),
    [title, setTitle] = useState(""),
    [postCaption, setPostCaption] = useState(""),
    [postTags, setPostTags] = useState(""),
    [author, setAuthor] = useState(""),
    [account, setAccount] = useState(""),
    [platform, setPlatform] = useState(""),
    [published, setPublished] = useState(""),
    [metrics, setMetrics] = useState("{}"),
    [tab, setTab] = useState("overview"),
    [editing, setEditing] = useState<Row | null>(null),
    [json, setJson] = useState(""),
    [busy, setBusy] = useState(false),
    [editingTranscript, setEditingTranscript] = useState(false);
  const video = useRef<HTMLVideoElement>(null),
    prev = useRef("");
  async function load() {
    try {
      const r = await api("/cases/" + id);
      setItem(r);
      setText(r.transcript || "");
      setNotes(r.notes || "");
      setTags((r.tags || []).join("，"));
      setCategory(r.category || "");
      setTitle(r.title);
      setPostCaption(r.publication_caption || "");
      setPostTags(
        (r.publication_hashtags || []).map((t: string) => "#" + t).join(" "),
      );
      setAuthor(r.author || "");
      setAccount(r.account || "");
      setPlatform(r.platform || "本地");
      setPublished(r.published_at || "");
      setMetrics(JSON.stringify(r.metrics || {}, null, 2));
    } catch (e) {
      onError(e);
    }
  }
  useEffect(() => {
    load();
  }, [id]);
  useEffect(() => {
    const signature = tasks
      .filter((t) => t.resource_id === id)
      .map((t) => t.id + t.status)
      .join();
    if (prev.current && signature !== prev.current) load();
    prev.current = signature;
  }, [tasks]);
  async function attachVideo(file: File) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/cases/" + id + "/video", "POST", form);
      await load();
      onNotice(
        "视频已附加到当前案例，正在提取逐字稿和关键帧；标题及原链接保留",
      );
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  async function run(type: string) {
    try {
      await api("/cases/" + id + "/analyze", "POST", {
        type,
        request_key: key(),
      });
      onNotice("已加入本地分析队列");
    } catch (e) {
      onError(e);
    }
  }
  async function save() {
    setBusy(true);
    try {
      const r = await api("/cases/" + id, "PATCH", {
        title,
        author,
        account,
        platform,
        published_at: published,
        transcript: text,
        notes,
        tags: tags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean),
        category,
        metrics: JSON.parse(metrics),
      });
      setItem(r);
      onNotice(
        r.sync?.status === "conflict"
          ? "研究笔记已有人工修改，更新内容保存为冲突副本"
          : "已保存逐字稿与案例资料",
      );
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }
  async function cover(file: File) {
    try {
      const f = new FormData();
      f.append("file", file);
      await api("/cases/" + id + "/cover", "POST", f);
      await load();
      onNotice("封面已保存");
    } catch (e) {
      onError(e);
    }
  }
  function seek(t: number) {
    if (video.current) {
      video.current.currentTime = t;
      video.current.play();
    }
  }
  if (!item) return <Empty>正在读取案例…</Empty>;
  const analyses = (item.analyses || []).filter((a: Row) => a.type === tab);
  const caseTasks = tasks.filter(
    (t) => t.resource_id === id && t.kind !== "metadata",
  );
  const task =
    caseTasks.find((t) => ["queued", "running"].includes(t.status)) ||
    caseTasks[0];
  return (
    <>
      <button className="text-button back" onClick={onBack}>
        <ArrowLeft size={16} />
        返回研究所
      </button>
      <div className="detail-intro">
        <figure className="detail-cover">
          {item.cover ? <img src={media(item.cover)} alt="原视频封面" /> : <div className="detail-cover-empty"><FileText size={28} /><span>尚未获取封面</span></div>}
          <figcaption>原视频封面</figcaption>
        </figure>
      <div className="page-heading detail-heading">
        <div>
          <div className="row gap">
            <Badge>{item.platform}</Badge>
            <span className="muted">
              案例 {id.slice(0, 8)} · {stamp(item.created_at)}
            </span>
          </div>
          <h1>视频研究工作台</h1>
        </div>
        <div className="row gap">
          {item.source_url && (
            <a
              className="button"
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
            >
              原始视频
              <ExternalLink size={15} />
            </a>
          )}
          <button className="primary" onClick={onCreate}>
            <PenLine size={16} />
            用此案例创作
          </button>
        </div>
      </div>
      </div>
      <div className="tabs research-tabs" role="tablist" aria-label="研究栏目">
        {[
          ["overview", "视频总览"],
          ["video", "文案研究"],
          ["title", "标题研究"],
          ["cover", "封面研究"],
        ].map(([v, l]) => (
          <button
            key={v}
            role="tab"
            aria-selected={tab === v}
            className={tab === v ? "selected" : ""}
            onClick={() => setTab(v)}
          >
            {l}
          </button>
        ))}
      </div>
      {task && (
        <div
          className={
            "task-banner " + (task.status === "failed" ? "failed" : "")
          }
        >
          <span>
            {task.status === "succeeded"
              ? "✓"
              : task.status === "failed"
                ? "!"
                : "◌"}{" "}
            {task.stage}
          </span>
          <span>{task.error || Math.round(task.progress * 100) + "%"}</span>
          {["failed", "interrupted"].includes(task.status) && (
            <button
              onClick={() =>
                api("/tasks/" + task.id + "/resume", "POST")
                  .then(() => onNotice("已提交重试或状态查询"))
                  .catch(onError)
              }
            >
              重试 / 查询
            </button>
          )}
        </div>
      )}
      {task && <ResearchProgress task={task} />}
      <div key={tab} className="research-content" role="tabpanel" aria-label={{overview: "视频总览", video: "文案研究", title: "标题研究", cover: "封面研究"}[tab]}>
      {tab === "overview" ? (
        <VideoOverview
          item={item}
          tasks={tasks}
          onNotice={onNotice}
          onError={onError}
        />
      ) : tab === "cover" ? (
        <CoverResearch
          id={id}
          tasks={tasks}
          onError={onError}
          onNotice={onNotice}
        />
      ) : (
        <div key={tab} className={"research-layout research-" + tab}>
          {tab !== "video" && (
            <section className="video-column">
              {tab === "title" ? (
                <div className="panel">
                  <h2>原视频发布信息</h2>
                  <p className="hint">
                    研究真实发布文字及其 #
                    话题。项目名称只作卡片命名，不参与任何研究。话题必须与原视频的
                    # 文本核验。
                  </p>
                  <label>
                    发布文案
                    <textarea
                      rows={6}
                      value={postCaption}
                      onChange={(e) => setPostCaption(e.target.value)}
                      placeholder="视频发布时填写的文案，不是口播逐字稿"
                    />
                  </label>
                  <label>
                    话题标签
                    <input
                      value={postTags}
                      onChange={(e) => setPostTags(e.target.value)}
                      placeholder="#标签1 #标签2，空格分隔"
                    />
                  </label>
                  <p className="hint">
                    来源：{item.publication_source || "未知，待补充"}
                  </p>
                  {item.publication_raw && (
                    <details>
                      <summary>查看服务返回的发布原文</summary>
                      <p>{item.publication_raw}</p>
                    </details>
                  )}
                  <button
                    className="primary"
                    onClick={async () => {
                      try {
                        await api("/cases/" + id, "PATCH", {
                          publication_caption: postCaption,
                          publication_hashtags: Array.from(
                            postTags.matchAll(
                              /#([^#\s，。！？、,;；:：!?.]+)/g,
                            ),
                            (m) => m[1],
                          ),
                        });
                        await load();
                        onNotice("已保存发布文案和 # 话题，可开始研究");
                      } catch (e) {
                        onError(e);
                      }
                    }}
                  >
                    保存发布信息
                  </button>
                </div>
              ) : (
                <div className="video-player">
                  {tab === "cover" ? (
                    item.cover ? (
                      <img src={media(item.cover)} alt="案例封面" />
                    ) : (
                      <Empty>
                        尚未取得封面，请上传图片或选择关键帧后重试封面研究。
                      </Empty>
                    )
                  ) : item.video ? (
                    <video
                      ref={video}
                      controls
                      preload="metadata"
                      src={media(item.video)}
                      poster={item.cover ? media(item.cover) : undefined}
                    />
                  ) : item.cover ? (
                    <img src={media(item.cover)} alt="案例封面" />
                  ) : (
                    <Empty>
                      {item.source_url
                        ? item.ingestion
                          ? "链接逐字稿已获取；原服务未返回视频文件，可打开原链接查看画面"
                          : "链接素材尚未取得，可上传本地视频继续研究"
                        : "可上传视频、封面或手动录入文案"}
                    </Empty>
                  )}
                </div>
              )}
              {tab === "video" && !item.video && (
                <label className="upload-inline video-fallback">
                  <Upload size={17} />
                  {busy ? "视频上传中…" : "上传本地视频，继续此案例"}
                  <input
                    aria-label="上传本地视频继续当前案例"
                    type="file"
                    accept="video/*,.mkv"
                    disabled={busy}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) attachVideo(file);
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
              {tab !== "title" && (
                <>
                  <div className="media-meta">
                    <span>
                      <Clock size={14} />
                      {item.duration
                        ? item.duration.toFixed(1) + " 秒"
                        : "时长未知"}
                    </span>
                    <span>
                      {item.width
                        ? item.width + " × " + item.height
                        : "尺寸未知"}
                    </span>
                  </div>
                  <section className="panel">
                    <div className="section-head compact">
                      <h2>关键帧 · 时间轴</h2>
                      {item.video && (
                        <button
                          className="icon"
                          aria-label="重新提取与转写"
                          onClick={() =>
                            api("/cases/" + id + "/process", "POST", {
                              type: "process",
                              request_key: key(),
                            })
                              .then(() => onNotice("已加入重新处理队列"))
                              .catch(onError)
                          }
                        >
                          <RefreshCw size={15} />
                        </button>
                      )}
                    </div>
                    <div className="frames">
                      {(item.frames || []).map((f: any) => (
                        <div key={f.path}>
                          <button onClick={() => seek(f.time)}>
                            <img
                              src={media(f.path)}
                              alt={f.time + "秒关键帧"}
                            />
                            <span>{f.time.toFixed(1)}s</span>
                          </button>
                          <button
                            className="text-button"
                            onClick={() =>
                              api("/cases/" + id, "PATCH", { cover: f.path })
                                .then(load)
                                .catch(onError)
                            }
                          >
                            设为封面
                          </button>
                        </div>
                      ))}
                    </div>
                    <label className="upload-inline">
                      <Upload size={15} />
                      上传封面
                      <input
                        aria-label="上传封面图片"
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={(e) => {
                          if (e.target.files?.[0]) cover(e.target.files[0]);
                        }}
                      />
                    </label>
                  </section>
                </>
              )}
              {tab === "video" && (
                <details className="panel">
                  <summary>案例资料与公开指标</summary>
                  <label>
                    作者
                    <input
                      value={author}
                      onChange={(e) => setAuthor(e.target.value)}
                    />
                  </label>
                  <label>
                    账号
                    <input
                      value={account}
                      onChange={(e) => setAccount(e.target.value)}
                    />
                  </label>
                  <label>
                    平台
                    <input
                      value={platform}
                      onChange={(e) => setPlatform(e.target.value)}
                    />
                  </label>
                  <label>
                    发布时间（未知可留空）
                    <input
                      value={published}
                      onChange={(e) => setPublished(e.target.value)}
                    />
                  </label>
                  <label>
                    分类
                    <input
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    />
                  </label>
                  <label>
                    标签（逗号分隔）
                    <input
                      value={tags}
                      onChange={(e) => setTags(e.target.value)}
                    />
                  </label>
                  <label>
                    公开指标 JSON
                    <textarea
                      rows={9}
                      value={metrics}
                      onChange={(e) => setMetrics(e.target.value)}
                    />
                  </label>
                  <p className="hint">
                    保留 source 与 collected_at；未知值填写
                    null，不推算缺失指标。
                  </p>
                  <button onClick={save} disabled={busy}>
                    <Save size={15} />
                    保存资料
                  </button>
                </details>
              )}
            </section>
          )}
          {tab === "video" && (
            <section className="transcript-column panel">
              <div className="section-head compact">
                <h2>口播逐字稿</h2>
                <Badge>可编辑</Badge>
              </div>
              <p className="hint">
                逐字稿保存在 Obsidian；外部修改后将检测冲突。
              </p>
              <button
                className="text-button"
                onClick={() => {
                  if (!editingTranscript && text === item.transcript)
                    setText(
                      transcriptParagraphs(
                        text,
                        item.segments || [],
                        item.transcript_edited,
                      )
                        .map((p) => p.text)
                        .join("\n\n"),
                    );
                  setEditingTranscript(!editingTranscript);
                }}
              >
                {editingTranscript ? "完成编辑，预览分段" : "编辑原文"}
              </button>
              {editingTranscript ? (
                <textarea
                  className="transcript-editor"
                  aria-label="口播逐字稿"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="每个自然段之间空一行"
                />
              ) : (
                <div
                  className="transcript-paragraphs"
                  aria-label="分段口播字幕"
                >
                  {transcriptParagraphs(
                    text,
                    item.segments || [],
                    item.transcript_edited || text !== item.transcript,
                  ).map((p, i) => (
                    <article key={i}>
                      {p.start !== undefined && (
                        <small>
                          {p.start.toFixed(1)}–{p.end?.toFixed(1)} 秒
                        </small>
                      )}
                      <p>{p.text}</p>
                    </article>
                  ))}
                </div>
              )}
              <label>
                我的研究备注
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={4}
                  placeholder="记下你的观察、疑问或下一步验证…"
                />
              </label>
              <button className="primary" disabled={busy} onClick={save}>
                <Save size={16} />
                保存修改
              </button>
              {item.note?.uri && (
                <a className="note-link" href={item.note.uri}>
                  <FileText size={15} />在 Obsidian 打开研究笔记
                  <ArrowUpRight size={15} />
                </a>
              )}
              {item.note?.status === "conflict" && (
                <div className="alert error">
                  存在人工修改冲突，新报告位于 {item.note.conflict}
                </div>
              )}
            </section>
          )}
          <section className="analysis-column panel">
            <div className="section-head compact">
              <h2>
                {tab === "video"
                  ? "文案研究"
                  : tab === "title"
                    ? "标题研究"
                    : "封面研究"}
              </h2>
              <Badge>本地 AI</Badge>
            </div>
            <button className="analysis-run" onClick={() => run(tab)}>
              <RefreshCw size={16} />
              {analyses.length
                ? "重新分析 · 保留旧版"
                : "开始分析" + (tab === "cover" ? "封面" : "")}
            </button>
            {!analyses.length ? (
              <Empty>分析结论会附带原文依据或时间戳，支持人工修订。</Empty>
            ) : (
              analyses.map((a: Row) => (
                <details
                  className="analysis-version"
                  open={a.id === analyses[0].id}
                  key={a.id}
                >
                  <summary>
                    {a.human ? "人工修订" : "AI 分析"} · {stamp(a.created_at)}
                  </summary>
                  <div className="model-meta">
                    {a.model} · {a.prompt_version}
                  </div>
                  {tab === "title" &&
                    a.prompt_version !== "virallab-research-v1.4" && (
                      <p className="hint">
                        历史版本使用旧命名或标签口径，仅供追溯；请以最新发布文案及核验标签结果为准。
                      </p>
                    )}
                  <JsonView
                    value={Object.fromEntries(
                      Object.entries(a.result).filter(([field]) =>
                        tab === "video"
                          ? !/标题|封面|构图|色彩/.test(field)
                          : tab === "title"
                            ? !/封面|构图|色彩|视觉|发布标题|标题字数|标题结构/.test(
                                field,
                              )
                            : true,
                      ),
                    )}
                  />
                  <button
                    className="text-button"
                    onClick={() => {
                      setEditing(a);
                      setJson(JSON.stringify(a.result, null, 2));
                    }}
                  >
                    <PenLine size={14} />
                    修订并保存新版本
                  </button>
                </details>
              ))
            )}
          </section>
        </div>
      )}
      </div>
      {editing && (
        <Modal title="修订分析 · 保留原版本" onClose={() => setEditing(null)}>
          <textarea
            className="code-editor"
            rows={20}
            aria-label="分析 JSON"
            value={json}
            onChange={(e) => setJson(e.target.value)}
          />
          <button
            className="primary"
            onClick={async () => {
              try {
                await api("/analyses/" + editing.id + "/versions", "POST", {
                  result: JSON.parse(json),
                });
                setEditing(null);
                load();
                onNotice("已保存人工修订版本");
              } catch (e) {
                onError(e);
              }
            }}
          >
            保存新版本
          </button>
        </Modal>
      )}
    </>
  );
}
