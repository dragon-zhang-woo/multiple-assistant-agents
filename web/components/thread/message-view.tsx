"use client";

import { FileText, Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentProfile, ThreadMessage } from "@/types/research";

interface MessageViewProps {
  message: ThreadMessage;
  agents: AgentProfile[];
  onSelectArtifact: (artifactId: string) => void;
}

export function MessageView({
  message,
  agents,
  onSelectArtifact
}: MessageViewProps) {
  const agent = agents.find((item) => item.id === message.agentId);

  if (message.role === "user") {
    return (
      <article className="flex justify-end">
        <div className="max-w-[82%] rounded-lg border border-border bg-accent px-4 py-3 text-sm leading-7">
          {message.content}
        </div>
      </article>
    );
  }

  return (
    <article className="group">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          {agent?.name ?? "Assistant"} · {message.createdAt}
        </div>
        <div className="flex opacity-0 transition-opacity group-hover:opacity-100">
          <Button variant="quiet" size="sm">
            Copy
          </Button>
        </div>
      </div>
      <div className="paper-prose whitespace-pre-line text-foreground">
        {message.content}
      </div>
      {(message.citations?.length || message.artifactIds?.length) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {message.citations?.map((citation) => (
            <span
              key={citation}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-background/45 px-2 py-1 text-xs text-muted-foreground"
            >
              <Quote className="h-3 w-3" />
              {citation}
            </span>
          ))}
          {message.artifactIds?.map((artifactId) => (
            <button
              key={artifactId}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border border-border bg-paper px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              )}
              onClick={() => onSelectArtifact(artifactId)}
            >
              <FileText className="h-3 w-3" />
              Open {artifactId}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
