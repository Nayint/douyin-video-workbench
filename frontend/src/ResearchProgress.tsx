import { Check, LoaderCircle, AlertCircle } from "lucide-react";
import type { Row } from "./api";

export function ResearchProgress({ task }: { task: Row }) {
  if (!["research_all", "link", "process"].includes(task.kind)) return null;
  const stage = task.stage || "";
  const finished: string[] = task.result?.completed || [];
  const failed = ["failed", "interrupted"].includes(task.status);
  const succeeded = task.status === "succeeded";
  const research = /文案研究|标题研究|封面研究/.test(stage) || finished.length > 0;
  const transcribing = /转写|转录|整理内容|整理格式|保存结果/.test(stage);
  const current = /封面研究/.test(stage) ? 4 : /标题研究/.test(stage) ? 3 : /文案研究/.test(stage) ? 2 : transcribing ? 1 : 0;
  const steps = [
    {label: "获取素材", done: succeeded || research || transcribing},
    {label: "转写口播", done: succeeded || research},
    {label: "文案研究", done: succeeded || finished.includes("video")},
    {label: "标题研究", done: succeeded || finished.includes("title")},
    {label: "封面研究", done: succeeded || finished.includes("cover_visual")},
  ].slice(0, task.kind === "research_all" ? 5 : 2);
  return <ol className="research-progress" aria-label="真实分析阶段">
    {steps.map((step, index) => {
      const state = step.done ? "done" : task.status === "running" && current === index ? "active" : "waiting";
      return <li key={step.label} data-state={state}>
        <span className="stage-symbol">{step.done ? <Check size={15} /> : state === "active" ? <LoaderCircle size={15} className="spin" /> : <span>{index + 1}</span>}</span>
        <span>{step.label}</span>
      </li>;
    })}
    {failed && <li className="progress-stopped"><AlertCircle size={15} />已暂停，请查看错误并重试</li>}
  </ol>;
}
