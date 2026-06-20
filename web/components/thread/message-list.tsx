"use client";

import { EmptyState } from "@/components/thread/empty-state";
import { MessageView } from "@/components/thread/message-view";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentProfile, ThreadMessage } from "@/types/research";

interface MessageListProps {
  messages: ThreadMessage[];
  agents: AgentProfile[];
  onSelectArtifact: (artifactId: string) => void;
  runError: string;
}

export function MessageList({
  messages,
  agents,
  onSelectArtifact,
  runError
}: MessageListProps) {
  if (messages.length === 0) {
    return <EmptyState />;
  }

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-7 px-5 py-8">
        {runError && (
          <div className="rounded-md border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
            {runError}
          </div>
        )}
        {messages.map((message) => (
          <MessageView
            key={message.id}
            message={message}
            agents={agents}
            onSelectArtifact={onSelectArtifact}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
