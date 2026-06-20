import { BookOpen, PenLine, Search } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-6">
      <div className="max-w-xl text-center">
        <div className="text-sm font-medium text-muted-foreground">
          Research Agent Workbench
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-normal">
          把科研问题交给一组安静工作的 Agent。
        </h1>
        <p className="mt-3 text-sm leading-7 text-muted-foreground">
          Planner 拆解任务，Scholar 检索论文，Reader 抽取证据，Critic 反思局限，Writer 生成右侧 artifact。
        </p>
        <div className="mt-8 grid gap-3 text-left sm:grid-cols-3">
          {[
            { icon: Search, label: "检索", detail: "arXiv queries" },
            { icon: BookOpen, label: "阅读", detail: "paper matrix" },
            { icon: PenLine, label: "写作", detail: "survey artifact" }
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-md border border-border bg-background/45 p-3"
            >
              <item.icon className="h-4 w-4 text-muted-foreground" />
              <div className="mt-3 text-sm font-medium">{item.label}</div>
              <div className="mt-1 text-xs text-muted-foreground">{item.detail}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
