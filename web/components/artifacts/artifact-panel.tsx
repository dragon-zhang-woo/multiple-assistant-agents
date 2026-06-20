"use client";

import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { useState } from "react";
import { ArtifactRenderer } from "@/components/artifacts/artifact-renderer";
import { ArtifactVersionPicker } from "@/components/artifacts/artifact-version-picker";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { Artifact } from "@/types/research";

interface ArtifactPanelProps {
  artifacts: Artifact[];
  activeArtifact?: Artifact;
  activeArtifactId: string;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  onSelectArtifact: (artifactId: string) => void;
}

export function ArtifactPanel({
  artifacts,
  activeArtifact,
  activeArtifactId,
  collapsed,
  onCollapsedChange,
  onSelectArtifact
}: ArtifactPanelProps) {
  const artifact = activeArtifact ?? artifacts[0];

  if (collapsed) {
    return (
      <aside className="hidden h-full w-12 shrink-0 border-l border-border bg-background lg:flex lg:flex-col lg:items-center lg:py-3">
        <Button
          variant="quiet"
          size="icon"
          onClick={() => onCollapsedChange(false)}
          aria-label="展开 Artifact 面板"
        >
          <PanelRightOpen className="h-4 w-4" />
        </Button>
      </aside>
    );
  }

  return (
    <aside className="hidden h-full w-[480px] shrink-0 border-l border-border bg-background lg:flex lg:flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Artifacts</div>
          <div className="truncate text-xs text-muted-foreground">
            reports, matrices, and code
          </div>
        </div>
        <Button
          variant="quiet"
          size="icon"
          onClick={() => onCollapsedChange(true)}
          aria-label="折叠 Artifact 面板"
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </header>
      <div className="flex shrink-0 gap-1 border-b border-border px-3 py-2">
        {artifacts.map((item) => (
          <button
            key={item.id}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              item.id === activeArtifactId && "bg-accent text-foreground"
            )}
            onClick={() => onSelectArtifact(item.id)}
          >
            {item.title}
          </button>
        ))}
      </div>
      {artifact && (
        <ArtifactContent key={artifact.id} artifact={artifact} />
      )}
    </aside>
  );
}

function ArtifactContent({ artifact }: { artifact: Artifact }) {
  const latestVersion = artifact.versions[artifact.versions.length - 1];
  const selectedVersion = latestVersion ?? artifact.versions[0];

  return (
    <VersionedArtifact artifact={artifact} initialVersionId={selectedVersion.id} />
  );
}

function VersionedArtifact({
  artifact,
  initialVersionId
}: {
  artifact: Artifact;
  initialVersionId: string;
}) {
  const [activeVersionId, setActiveVersionId] = useState(initialVersionId);
  const version =
    artifact.versions.find((item) => item.id === activeVersionId) ??
    artifact.versions[0];

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="p-4">
        <ArtifactVersionPicker
          artifact={artifact}
          activeVersionId={version.id}
          onVersionChange={(next) => setActiveVersionId(next.id)}
        />
        <ArtifactRenderer artifact={artifact} version={version} />
      </div>
    </ScrollArea>
  );
}
