"use client";

import { Maximize2, Minimize2, PanelRightClose, PanelRightOpen } from "lucide-react";
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
  widthMode: ArtifactWidthMode;
  onWidthModeChange: (mode: ArtifactWidthMode) => void;
}

type ArtifactWidthMode = "compact" | "comfortable" | "wide";

const widthClass: Record<ArtifactWidthMode, string> = {
  compact: "w-[480px]",
  comfortable: "w-[640px]",
  wide: "w-[760px]"
};

export function ArtifactPanel({
  artifacts,
  activeArtifact,
  activeArtifactId,
  collapsed,
  onCollapsedChange,
  onSelectArtifact,
  widthMode,
  onWidthModeChange
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
    <aside
      className={cn(
        "hidden h-full shrink-0 border-l border-border/80 bg-background lg:flex lg:flex-col",
        widthClass[widthMode]
      )}
    >
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 px-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Artifacts</div>
          <div className="truncate text-xs text-muted-foreground">
            reports, matrices, and code
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="quiet"
            size="icon"
            onClick={() =>
              onWidthModeChange(widthMode === "wide" ? "comfortable" : "wide")
            }
            aria-label={widthMode === "wide" ? "Close wide" : "Open wide"}
            title={widthMode === "wide" ? "Close wide" : "Open wide"}
          >
            {widthMode === "wide" ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="quiet"
            size="icon"
            onClick={() => onCollapsedChange(true)}
            aria-label="折叠 Artifact 面板"
          >
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
      </header>
      {artifacts.length > 0 && (
        <div className="flex shrink-0 items-center gap-3 overflow-x-auto border-b border-border/80 px-4 py-2 quiet-scrollbar">
          {artifacts.map((item) => (
            <button
              key={item.id}
              className={cn(
                "whitespace-nowrap border-b border-transparent py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground",
                item.id === activeArtifactId && "border-foreground/45 text-foreground"
              )}
              onClick={() => onSelectArtifact(item.id)}
            >
              {item.title}
            </button>
          ))}
          <div className="ml-auto flex shrink-0 rounded-md border border-border/80 p-0.5">
            {(["compact", "comfortable", "wide"] as const).map((mode) => (
              <button
                key={mode}
                className={cn(
                  "rounded px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent hover:text-foreground",
                  widthMode === mode && "bg-accent text-foreground"
                )}
                onClick={() => onWidthModeChange(mode)}
              >
                {mode === "compact" ? "S" : mode === "comfortable" ? "M" : "L"}
              </button>
            ))}
          </div>
        </div>
      )}
      {artifact ? (
        <ArtifactContent key={artifact.id} artifact={artifact} />
      ) : (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6 text-center text-sm leading-6 text-muted-foreground">
          运行一个研究任务后，这里会显示 survey、mindmap、literature matrix 和 run log。
        </div>
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
