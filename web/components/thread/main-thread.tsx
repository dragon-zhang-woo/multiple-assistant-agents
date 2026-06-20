"use client";

import { PanelRightOpen } from "lucide-react";
import { AgentStatusStrip } from "@/components/thread/agent-status-strip";
import { AgentTraceDrawer } from "@/components/thread/agent-trace-drawer";
import { Composer } from "@/components/thread/composer";
import { MessageList } from "@/components/thread/message-list";
import { Button } from "@/components/ui/button";
import type {
  AgentProfile,
  AgentTraceEvent,
  ResearchProject,
  ThreadMessage
} from "@/types/research";

interface MainThreadProps {
  project: ResearchProject;
  agents: AgentProfile[];
  messages: ThreadMessage[];
  trace: AgentTraceEvent[];
  traceOpen: boolean;
  onTraceOpenChange: (open: boolean) => void;
  onSendMessage: (content: string) => void;
  onSelectArtifact: (artifactId: string) => void;
}

export function MainThread({
  project,
  agents,
  messages,
  trace,
  traceOpen,
  onTraceOpenChange,
  onSendMessage,
  onSelectArtifact
}: MainThreadProps) {
  return (
    <section className="flex h-full min-w-0 flex-1 flex-col bg-paper">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-5">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{project.name}</div>
          <div className="truncate text-xs text-muted-foreground">
            {project.description}
          </div>
        </div>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => onTraceOpenChange(!traceOpen)}
        >
          <PanelRightOpen className="h-4 w-4" />
          Trace
        </Button>
      </header>
      <AgentStatusStrip agents={agents} />
      <div className="relative flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <MessageList
            messages={messages}
            agents={agents}
            onSelectArtifact={onSelectArtifact}
          />
          <Composer onSendMessage={onSendMessage} />
        </div>
        <AgentTraceDrawer
          open={traceOpen}
          trace={trace}
          agents={agents}
          onOpenChange={onTraceOpenChange}
        />
      </div>
    </section>
  );
}
