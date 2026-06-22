interface CodeArtifactProps {
  code: string;
  language: string;
}

export function CodeArtifact({ code, language }: CodeArtifactProps) {
  return (
    <div className="overflow-hidden rounded-md border border-border/80 bg-paper">
      <div className="border-b border-border/80 bg-muted px-3 py-2 text-xs text-muted-foreground">
        {language}
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6 quiet-scrollbar">
        <code>{code}</code>
      </pre>
    </div>
  );
}
