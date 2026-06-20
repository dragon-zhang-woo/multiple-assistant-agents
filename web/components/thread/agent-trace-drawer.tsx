"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { AgentProfile, AgentTraceEvent } from "@/types/research";

interface AgentTraceDrawerProps {
  open: boolean;
  trace: AgentTraceEvent[];
  agents: AgentProfile[];
  onOpenChange: (open: boolean) => void;
}

export function AgentTraceDrawer({
  open,
  trace,
  agents,
  onOpenChange
}: AgentTraceDrawerProps) {
  return (
    <aside
      className={cn(
        "pointer-events-none absolute inset-y-3 right-3 z-20 hidden w-[340px] overflow-hidden rounded-md border border-border bg-background opacity-0 transition-[opacity,transform] duration-150 xl:flex xl:flex-col",
        open && "pointer-events-auto translate-x-0 opacity-100",
        !open && "translate-x-3"
      )}
      aria-hidden={!open}
    >
      <div className="flex h-12 items-center justify-between border-b border-border px-4">
        <div>
          <div className="text-sm font-medium">Agent Trace</div>
          <div className="text-xs text-muted-foreground">tool calls and handoffs</div>
        </div>
        <Button variant="quiet" size="icon" onClick={() => onOpenChange(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {trace.map((event) => {
            const agent = agents.find((item) => item.id === event.agentId);
            return (
              <div key={event.id} className="rounded-md border border-border bg-paper p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium">{agent?.name}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {event.timestamp}
                  </div>
                </div>
                <div className="mt-2 text-sm font-medium">{event.title}</div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {event.detail}
                </p>
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </aside>
  );
}
