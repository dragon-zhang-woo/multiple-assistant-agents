"use client";

import { useMemo } from "react";
import type { Artifact, ArtifactVersion } from "@/types/research";

interface ArtifactVersionPickerProps {
  artifact: Artifact;
  activeVersionId: string;
  onVersionChange?: (version: ArtifactVersion) => void;
}

export function ArtifactVersionPicker({
  artifact,
  activeVersionId,
  onVersionChange
}: ArtifactVersionPickerProps) {
  const active = useMemo(
    () =>
      artifact.versions.find((version) => version.id === activeVersionId) ??
      artifact.versions[0],
    [artifact.versions, activeVersionId]
  );

  return (
    <div className="mb-4 rounded-md border border-border bg-paper p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{artifact.title}</div>
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {active.summary}
          </div>
        </div>
        <select
          value={active.id}
          onChange={(event) => {
            const next = artifact.versions.find(
              (version) => version.id === event.target.value
            );
            if (next) {
              onVersionChange?.(next);
            }
          }}
          className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none"
        >
          {artifact.versions.map((version) => (
            <option key={version.id} value={version.id}>
              {version.label}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-2 text-[11px] text-muted-foreground">
        Updated {active.createdAt}
      </div>
    </div>
  );
}
