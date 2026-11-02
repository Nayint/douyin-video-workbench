import { useEffect, type ReactNode } from "react";
import { api, key, stamp, type Row, media } from "./api";
export function VideoOverview({
  item,
  tasks,
  onNotice,
  onError,
  headerControl,
}: {
  headerControl?: ReactNode;
  item: Row;
  tasks: Row[];
  onNotice: (s: string) => void;
  onError: (e: unknown) => void;
}) {
  const active = tasks.some(
    (t) =>
      t.resource_id === item.id && ["queued", "running"].includes(t.status),
  );
  const refresh = () =>
    api("/cases/" + item.id + "/metadata", "POST", {
      type: "metadata",
      request_key: key(),
    })
      .then(() => onNotice("正在从原视频读取详情，平台未公开的数据不会推算"))
      .catch(onError);
  useEffect(() => {
    if (item.source_url && !item.metadata_collected_at) refresh();
  }, [item.id]);
  const unknown = "平台未返回";
  return (
    <div className="collected-detail-grid">
      <section className="panel">
        <h2>视频信息</h2>
        {headerControl}
        <dl className="material-facts">
          <dt>平台</dt>
          <dd>{item.platform || "待识别"}</dd>
          <dt>原作者</dt>
          <dd>{item.author || unknown}</dd>
          <dt>账号</dt>
          <dd>{item.account || unknown}</dd>
          <dt>发布时间</dt>
          <dd>{item.published_at ? stamp(item.published_at) : unknown}</dd>
          <dt>视频时长</dt>
          <dd>
            {item.duration ? item.duration.toFixed(1) + " 秒" : "尚未取得"}
          </dd>
          <dt>画面尺寸</dt>
          <dd>
            {item.width && item.height
              ? item.width + " × " + item.height
              : "原视频未返回尺寸"}
          </dd>
          <dt>视频编号</dt>
          <dd>{item.source_video_id || "尚未取得"}</dd>
          <dt>原始链接</dt>
          <dd>
            {item.source_url ? (
              <a href={item.source_url} target="_blank" rel="noreferrer">
                {item.source_url}
              </a>
            ) : (
              "本地上传，无平台链接"
            )}
          </dd>
          <dt>收录时间</dt>
          <dd>{stamp(item.created_at)}</dd>
          <dt>平台分类</dt>
          <dd>{item.source_categories?.join("、") || "未返回分类"}</dd>
        </dl>
        {item.video && (
          <video
            className="collected-video"
            controls
            src={media(item.video)}
            poster={item.cover ? media(item.cover) : undefined}
          />
        )}
        <p className="hint">
          平台分类不作为话题标签；公开数据仅代表采集时点，不证明内容成功的原因。
        </p>
      </section>
      <section className="panel">
        <h2>公开互动数据</h2>
        <dl className="material-facts">
          {[
            ["点赞", "likes"],
            ["评论", "comments"],
            ["收藏", "favorites"],
            ["分享", "shares"],
          ].map(([label, k]) => (
            <div style={{ display: "contents" }} key={k}>
              <dt>{label}</dt>
              <dd>{item.metrics?.[k] ?? unknown}</dd>
            </div>
          ))}
          <dt>数据来源</dt>
          <dd>{item.metrics?.source || "尚未采集"}</dd>
          <dt>指标采集时间</dt>
          <dd>
            {item.metrics?.source
              ? stamp(item.metrics.collected_at)
              : "尚未采集"}
          </dd>
          <dt>详情来源</dt>
          <dd>{item.metadata_source || "尚未读取原视频详情"}</dd>
          <dt>详情采集时间</dt>
          <dd>
            {item.metadata_collected_at
              ? stamp(item.metadata_collected_at)
              : "尚未采集"}
          </dd>
        </dl>
        {item.metadata_error && (
          <p role="alert" className="task-error">
            {item.metadata_error}
          </p>
        )}
        {item.source_url && (
          <button disabled={active} onClick={refresh}>
            {active ? "任务处理中…" : "刷新视频信息"}
          </button>
        )}
        <h3>人工备注</h3>
        <p className="preserve-text">{item.notes || "暂无备注"}</p>
        <p className="hint">
          此处只汇总视频信息；发布文字、标签与口播内容分别放在对应研究栏目。
        </p>
      </section>
    </div>
  );
}
