import { CreationStory } from "./CreationStory";
import { ResearchDialog, type CardOrigin } from "./ResearchDialog";
import { workspaceRoute, workspaceHash } from "./workspaceRoute";
import { ProductLibrary } from "./ProductLibrary";
import { useState, useEffect, useRef, type CSSProperties } from "react";
import {
  FlaskConical,
  LayoutDashboard,
  Clapperboard,
  Library,
  PenLine,
  Settings,
  Search,
  Plus,
  Moon,
  Sun,
  ArrowUpRight,
  ChevronRight,
  CheckCircle2,
  Activity,
  Star,
  FileText,
  Layers,
  PanelLeft,
  RefreshCw,
} from "lucide-react";
import { api, stamp, key, type Row } from "./api";
import { Badge, ImportModal } from "./components";
import { CollectedDetail } from "./CollectedDetail";
import { CaseDetail } from "./CaseDetail";
import {
  Collection,
  TaskCenter,
  Drafts,
  ComparisonReports,
} from "./Collections";
import { Creation, SettingsPage } from "./Workspace";
const nav = [
  ["home", LayoutDashboard, "工作台"],
  ["collected", Clapperboard, "已收录视频"],
  ["library", Library, "研究所"],
  ["products", Layers, "产品库"],
  ["create", PenLine, "文案创作"],
  ["drafts", FileText, "原创文案"],
  ["tasks", Activity, "待处理任务"],
  ["settings", Settings, "系统设置"],
] as const;
export default function App() {
  const pageSurface = useRef<HTMLElement>(null);
  const cardOrigin = useRef<CardOrigin | null>(null);
  const [directoryWidth, setDirectoryWidth] = useState(() =>
    Math.max(
      180,
      Math.min(
        310,
        Number(localStorage.getItem("workspace-directory-width")) || 222,
      ),
    ),
  );
  useEffect(() => {
    localStorage.setItem("workspace-directory-width", String(directoryWidth));
  }, [directoryWidth]);
  const [creationCase, setCreationCase] = useState<string | null>(null);
  const [page, setPage] = useState(() => workspaceRoute(location.hash).page),
    [selected, setSelected] = useState<string | null>(
      () => workspaceRoute(location.hash).selected,
    ),
    [importing, setImporting] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [dark, setDark] = useState(
      localStorage.getItem("workspace-theme-v2") !== "light",
    ),
    [menu, setMenu] = useState(false);
  const [dashboard, setDashboard] = useState<any>(null),
    [cases, setCases] = useState<Row[]>([]),
    [tasks, setTasks] = useState<Row[]>([]),
    [query, setQuery] = useState(""),
    [favorite, setFavorite] = useState(false),
    [category, setCategory] = useState(""),
    [tag, setTag] = useState(""),
    [sort, setSort] = useState("updated_at"),
    [compared, setCompared] = useState<string[]>([]);
  const fail = (e: unknown) => setError(String(e).replace(/^Error: /, ""));
  async function refresh() {
    try {
      const [d, c, t] = await Promise.all([
        api("/dashboard"),
        api<Row[]>("/cases"),
        api<Row[]>("/tasks"),
      ]);
      setDashboard(d);
      setCases(c);
      setTasks(t);
    } catch (e) {
      fail(e);
    }
  }
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("workspace-theme-v2", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    history.replaceState(null, "", workspaceHash(page, selected));
  }, [page, selected]);
  useEffect(() => {
    const read = () => {
      const route = workspaceRoute(location.hash);
      setPage(route.page);
      setSelected(route.selected);
    };
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  useEffect(() => {
    const surface = pageSurface.current;
    if (page === "library") return;
    if (!surface || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Opacity preserves fixed menus and dialogs in their viewport coordinate space.
    const animation = surface.animate([{ opacity: 0.35 }, { opacity: 1 }], {
      duration: 280, easing: "cubic-bezier(.2,.8,.2,1)",
    });
    return () => animation.cancel();
  }, [page, selected]);
  function navigate(v: string) {
    setPage(v);
    setSelected(null);
    setMenu(false);
    setQuery("");
  }
  const open = (id: string) => {
    const element = Array.from(document.querySelectorAll<HTMLElement>("[data-case-id]")).find(el => el.dataset.caseId === id);
    cardOrigin.current = element ? { element, rect: element.getBoundingClientRect(), focus: element.contains(document.activeElement) ? document.activeElement as HTMLElement : element.querySelector<HTMLElement>("button") } : null;
    setPage(
      cases.find((c) => c.id === id)?.has_research ? "library" : "collected",
    );
    setSelected(id);
  };
  const visible = cases
    .filter(
      (c) =>
        (page === "library"
          ? c.has_research
          : ["home", "collected"].includes(page)
            ? !c.has_research
            : true) &&
        (!query ||
          JSON.stringify(c).toLowerCase().includes(query.toLowerCase())) &&
        (!favorite || c.favorite) &&
        (!category || c.category === category) &&
        (!tag || (c.tags || []).includes(tag)),
    )
    .sort((a, b) =>
      sort === "title"
        ? a.title.localeCompare(b.title)
        : sort === "duration"
          ? (b.duration || 0) - (a.duration || 0)
          : 0,
    );
  const current = selected
    ? page === "collected"
      ? "已收录视频"
      : "研究所"
    : nav.find((n) => n[0] === page)?.[2] || "研究所";
  const active = tasks.filter((t) => ["running", "queued"].includes(t.status));
  function feedback(s: string) {
    setError("");
    setNotice(s);
    refresh();
  }
  async function compare() {
    try {
      const selectedCases = cases.filter((c) => compared.includes(c.id));
      await api("/research", "POST", {
        type: "compare",
        request_key: key(),
        material: {
          cases: await Promise.all(
            selectedCases.map((c) => api("/cases/" + c.id)),
          ),
        },
      });
      feedback("案例比较任务已加入队列，完成后显示在研究所的对比报告中");
      navigate("library");
    } catch (e) {
      fail(e);
    }
  }
  return (
    <div
      className="app-shell"
      style={{ "--directory-width": directoryWidth + "px" } as CSSProperties}
    >
      <aside className={menu ? "sidebar expanded" : "sidebar"}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("home");
          }}
        >
          <div className="brand-mark">
            <FlaskConical size={24} />
          </div>
          <span>
            ViralLab<small>内容研究工作台</small>
          </span>
        </a>
        <div className="nav-label">研究与创作</div>
        <nav>
          {nav.map(([id, Icon, label]) => (
            <button
              key={id}
              className={page === id ? "nav-item current" : "nav-item"}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "library" && (
                <small>{cases.filter((c) => c.has_research).length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-chip">
            <i />
            本地工作空间<Badge>V1.0</Badge>
          </div>
          <p>积累好内容，找到自己的表达。</p>
          <button className="theme-toggle" onClick={() => setDark(!dark)}>
            {dark ? <Sun size={16} /> : <Moon size={16} />}切换
            {dark ? "浅色" : "深色"}模式
          </button>
        </div>
      </aside>
      <div
        className="directory-splitter"
        role="separator"
        aria-label="调整目录面板宽度"
        aria-orientation="vertical"
        aria-valuenow={directoryWidth}
        aria-valuemin={180}
        aria-valuemax={310}
        tabIndex={0}
        onKeyDown={(e) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
            e.preventDefault();
            setDirectoryWidth(
              e.key === "Home"
                ? 180
                : e.key === "End"
                  ? 310
                  : Math.max(
                      180,
                      Math.min(
                        310,
                        directoryWidth + (e.key === "ArrowRight" ? 10 : -10),
                      ),
                    ),
            );
          }
        }}
        onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId) && e.buttons === 1)
            setDirectoryWidth(Math.max(180, Math.min(310, e.clientX)));
        }}
      />
      <div className="main-shell">
        <header>
          <div className="row">
            <button
              className="icon mobile-menu"
              aria-label="展开导航"
              onClick={() => setMenu(!menu)}
            >
              <PanelLeft />
            </button>
            <span className="breadcrumb">
              <span className="workspace-label">ViralLab</span>
              <ChevronRight size={14} />
              <strong>{current}</strong>
            </span>
          </div>
          <div className="header-actions">
            <label className="search">
              <Search size={16} />
              <input
                aria-label="搜索案例"
                placeholder="搜索案例、标签、关键词"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  if (!["home", "library", "video", "cover"].includes(page))
                    setPage("library");
                }}
              />
            </label>
            <span className="local-status">
              <i />
              本机运行
            </span>
            <button
              className="primary small"
              onClick={() => setImporting(true)}
            >
              <Plus size={16} />
              导入视频
            </button>
          </div>
        </header>
        <main ref={pageSurface} data-page={page} data-detail={selected ? "true" : "false"}>
          {error && (
            <div role="alert" className="alert error">
              {error}
              <button aria-label="关闭错误" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              {notice}
              <button aria-label="关闭通知" onClick={() => setNotice("")}>
                ×
              </button>
            </div>
          )}
          {page === "home" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">工作台</div>
                  <h1>
                    工作台
                    <span className="title-dot">.</span>
                  </h1>
                  <p>收录值得研究的内容，写好下一条视频。</p>
                </div>
                <span className="date">
                  {new Date().toLocaleDateString("zh-CN", {
                    month: "long",
                    day: "numeric",
                    weekday: "long",
                  })}
                </span>
              </div>
              <section className="hero apple-web-hero">
                <CreationStory />
                <div className="hero-actions">
                  <button className="primary" onClick={() => setImporting(true)}>
                    <Plus size={17} />导入视频
                  </button>
                  <button onClick={() => navigate("create")}>
                    开始文案创作<ArrowUpRight size={17} />
                  </button>
                </div>
                <div className="creative-path" aria-label="创作流程">
                  <button onClick={() => navigate("collected")}><span className="path-number">01</span><strong>收录灵感</strong><span>留住值得研究的内容</span><ArrowUpRight size={18} /></button>
                  <button onClick={() => navigate("library")}><span className="path-number">02</span><strong>看懂表达</strong><span>研究文案、标题与封面</span><ArrowUpRight size={18} /></button>
                  <button onClick={() => navigate("create")}><span className="path-number">03</span><strong>写出自己的</strong><span>结合产品，让灵感成为文案</span><ArrowUpRight size={18} /></button>
                </div>
              </section>
              <div className="stats">
                {[
                  [Library, "已收录视频", dashboard?.total, "collected"],
                  [CheckCircle2, "已分析案例", dashboard?.analyzed, "library"],
                  [FileText, "原创文案", dashboard?.drafts_total, "drafts"],
                  [Activity, "待处理任务", dashboard?.pending, "tasks"],
                ].map(([Icon, label, value, target]: any) => (
                  <button
                    className="stat"
                    key={label}
                    onClick={() => navigate(target)}
                  >
                    <div>
                      <span>{label}</span>
                      <strong>
                        {value ?? "—"}
                        <small>{label === "待处理任务" ? "项" : "条"}</small>
                      </strong>
                    </div>
                    <Icon size={21} />
                  </button>
                ))}
              </div>
              <div className="home-columns">
                <section className="panel">
                  <div className="section-head compact">
                    <h2>最近创作</h2>
                    <button
                      className="icon"
                      aria-label="前往创作"
                      onClick={() => navigate("create")}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </div>
                  {dashboard?.drafts?.length ? (
                    dashboard.drafts.map((d: Row) => (
                      <button
                        className="list-row"
                        key={d.id}
                        onClick={() => navigate("drafts")}
                      >
                        <FileText size={17} />
                        <div>
                          <strong>{d.title || "口播文案 · " + d.id.slice(0, 8)}</strong>
                          <span>{stamp(d.created_at)}</span>
                        </div>
                        <ChevronRight size={15} />
                      </button>
                    ))
                  ) : (
                    <p className="subtle-empty">
                      选一个案例和一份产品资料，开始原创。
                    </p>
                  )}
                </section>
                <section className="panel">
                  <div className="section-head compact">
                    <h2>收藏案例</h2>
                    <Star size={17} />
                  </div>
                  {dashboard?.favorites?.length ? (
                    dashboard.favorites.map((c: Row) => (
                      <button
                        className="list-row"
                        key={c.id}
                        onClick={() => open(c.id)}
                      >
                        <Star size={17} />
                        <strong>{c.title}</strong>
                        <ChevronRight size={15} />
                      </button>
                    ))
                  ) : (
                    <p className="subtle-empty">
                      把值得反复研究的案例收藏在这里。
                    </p>
                  )}
                </section>
              </div>
              <section className="panel">
                <div className="section-head compact">
                  <h2>最近研究报告</h2>
                  <button
                    className="text-button"
                    onClick={() => navigate("library")}
                  >
                    查看报告
                    <ArrowUpRight size={15} />
                  </button>
                </div>
                {dashboard?.reports?.length ? (
                  dashboard.reports.map((a: Row) => (
                    <button
                      className="list-row"
                      key={a.id}
                      onClick={() =>
                        a.case_id ? open(a.case_id) : navigate("library")
                      }
                    >
                      <Activity size={17} />
                      <strong>
                        {{
                          video: "文案",
                          title: "标题",
                          cover: "封面提示词",
                          cover_visual: "封面",
                          compare: "案例比较",
                          suggest: "标题建议",
                        }[a.type as string] || "内容"}
                        {a.type === "cover" ? "" : "研究"}
                      </strong>
                      <span className="muted">
                        {a.model} · {stamp(a.created_at)}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="subtle-empty">
                    完成分析后，研究报告会出现在这里。
                  </p>
                )}
              </section>
            </>
          )}
          {["library", "collected"].includes(page) && (!selected || page === "library") && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">CONTENT LIBRARY</div>
                  <h1>{current}</h1>
                  <p>
                    {page === "cover"
                      ? "并排观察封面的主体、文字与视觉焦点。"
                      : "研究所仅展示已有研究结果的案例；未研究素材请到已收录视频。"}
                  </p>
                </div>
                <button className="primary" onClick={() => setImporting(true)}>
                  <Plus size={17} />
                  新增案例
                </button>
              </div>
              <div className="filters">
                <button
                  className={favorite ? "selected" : ""}
                  onClick={() => setFavorite(!favorite)}
                >
                  <Star size={15} />
                  仅收藏
                </button>
                <input
                  aria-label="按分类筛选"
                  placeholder="分类筛选"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                />
                <input
                  aria-label="按标签筛选"
                  placeholder="标签筛选"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                />
                <select
                  aria-label="排序"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="updated_at">最近更新</option>
                  <option value="title">标题排序</option>
                  <option value="duration">时长排序</option>
                </select>
                <button disabled={compared.length < 2} onClick={compare}>
                  比较 {compared.length} 个案例
                </button>
              </div>
              <Collection
                cases={visible}
                onOpen={open}
                onRefresh={refresh}
                onError={fail}
                onNotice={feedback}
                onSelection={setCompared}
              />
              {page === "library" && <ComparisonReports tasks={tasks} />}
            </>
          )}
          {selected && page === "collected" && (
            <CollectedDetail
              tasks={tasks}
              onResearch={() => setPage("library")}
              id={selected}
              onBack={() => setSelected(null)}
              onRefresh={refresh}
              onError={fail}
              onNotice={feedback}
            />
          )}
          {selected && page === "library" && (
            <ResearchDialog key={selected} origin={cardOrigin.current} onClose={() => setSelected(null)}>
            {(close) => <>
            {error && <div className="alert error" role="alert">{error}</div>}
            {notice && <div className="alert success" role="status">{notice}</div>}
            <CaseDetail
              id={selected}
              tasks={tasks}
              onBack={close}
              onError={fail}
              onNotice={feedback}
              onCreate={() => {
                setCreationCase(selected);
                navigate("create");
              }}
            /></>}
            </ResearchDialog>
          )}
          {page === "drafts" && <Drafts onError={fail} onNotice={feedback} />}
          {page === "tasks" && (
            <TaskCenter
              tasks={tasks}
              cases={cases}
              onOpen={open}
              onRefresh={refresh}
              onError={fail}
            />
          )}
          {page === "create" && (
            <Creation
              cases={cases}
              tasks={tasks}
              initialCase={creationCase}
              onError={fail}
              onNotice={feedback}
            />
          )}
          {page === "products" && (
            <ProductLibrary tasks={tasks} onError={fail} onNotice={feedback} />
          )}
          {page === "settings" && (
            <SettingsPage tasks={tasks} onError={fail} onNotice={feedback} />
          )}
          <footer>
            <span>
              <FlaskConical size={14} />
              ViralLab · 你的本地内容实验室
            </span>
            <span>公开指标仅供观察，AI 判断需要人工核实。</span>
          </footer>
        </main>
        {active.length > 0 && page !== "create" && (
          <div className="task-dock">
            <RefreshCw className="spin" size={16} />
            <strong>{active[0].stage}</strong>
            <span>{active.length} 项任务</span>
            <progress max={1} value={active[0].progress} />
          </div>
        )}
      </div>
      {importing && (
        <ImportModal
          onClose={() => setImporting(false)}
          onDone={(id, collectOnly) => {
            setError("");
            refresh();
            if (collectOnly) {
              navigate("collected");
              setNotice("已收录素材，尚未开始分析；可选择后点击分析");
            } else {
              open(id);
              setNotice("已收录并开始文案、标题和封面研究");
            }
          }}
          onError={fail}
        />
      )}
    </div>
  );
}
