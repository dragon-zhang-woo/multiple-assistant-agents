"use client";

import { Check, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentProfile, AgentStatus } from "@/types/research";

interface AgentStatusStripProps {
  agents: AgentProfile[];
}

const statusLabels: Record<AgentStatus, string> = {
  idle: "Idle",
  queued: "Queued",
  working: "Working",
  reviewing: "Reviewing",
  done: "Done",
  error: "Error"
};

export function AgentStatusStrip({ agents }: AgentStatusStripProps) {
  return (
    <div className="shrink-0 border-b border-border/70 bg-paper px-4 py-1.5">
      <div className="flex gap-2 overflow-x-auto quiet-scrollbar">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="min-w-[142px] rounded-md border border-border/75 bg-background/35 px-2.5 py-1.5"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <StatusIcon status={agent.status} />
                <span className="text-xs font-medium">{agent.name}</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {statusLabels[agent.status]}
              </span>
            </div>
            <div className="mt-1.5 h-0.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-foreground/45 transition-all"
                style={{ width: `${agent.progress}%` }}
              />
            </div>
            <div className="mt-1 truncate text-[10px] text-muted-foreground">
              {agent.currentTask}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: AgentStatus }) {
  if (status === "done") {
    return <Check className="h-3.5 w-3.5 text-foreground" />;
  }
  if (status === "working" || status === "reviewing") {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />;
  }
  if (status === "error") {
    return <Circle className="h-3.5 w-3.5 fill-muted text-foreground" />;
  }
  return (
    <Circle
      className={cn(
        "h-3.5 w-3.5 text-muted-foreground",
        status === "queued" && "fill-muted"
      )}
    />
  );
}
