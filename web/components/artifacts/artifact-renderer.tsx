import { CodeArtifact } from "@/components/artifacts/code-artifact";
import { LiteratureMatrix } from "@/components/artifacts/literature-matrix";
import { MarkdownArtifact } from "@/components/artifacts/markdown-artifact";
import type { Artifact, ArtifactVersion } from "@/types/research";

interface ArtifactRendererProps {
  artifact: Artifact;
  version: ArtifactVersion;
}

export function ArtifactRenderer({ artifact, version }: ArtifactRendererProps) {
  if (artifact.kind === "literature-matrix") {
    return <LiteratureMatrix rows={version.literature ?? []} />;
  }

  if (artifact.kind === "code") {
    return (
      <CodeArtifact
        code={version.content}
        language={version.language ?? "ts"}
      />
    );
  }

  return <MarkdownArtifact content={version.content} />;
}
