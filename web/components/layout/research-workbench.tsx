"use client";

import { ArtifactPanel } from "@/components/artifacts/artifact-panel";
import { ResearchSidebar } from "@/components/layout/research-sidebar";
import { MainThread } from "@/components/thread/main-thread";
import { useResearchThread } from "@/lib/hooks/use-research-thread";

export function ResearchWorkbench() {
  const thread = useResearchThread();

  return (
    <main className="h-screen overflow-hidden bg-background text-foreground">
      <div className="flex h-full min-w-0">
        <ResearchSidebar
          projects={thread.projects}
          activeProjectId={thread.activeProject.id}
          onSelectProject={thread.setActiveProjectId}
        />
        <MainThread
          project={thread.activeProject}
          agents={thread.agents}
          messages={thread.messages}
          trace={thread.trace}
          traceOpen={thread.traceOpen}
          onTraceOpenChange={thread.setTraceOpen}
          onSendMessage={thread.sendMessage}
          onSelectArtifact={thread.setActiveArtifactId}
        />
        <ArtifactPanel
          artifacts={thread.artifacts}
          activeArtifact={thread.activeArtifact}
          activeArtifactId={thread.activeArtifactId}
          collapsed={thread.artifactCollapsed}
          onCollapsedChange={thread.setArtifactCollapsed}
          onSelectArtifact={thread.setActiveArtifactId}
        />
      </div>
    </main>
  );
}
