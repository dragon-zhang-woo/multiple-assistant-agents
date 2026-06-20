interface CodeArtifactProps {
  code: string;
  language: string;
}

export function CodeArtifact({ code, language }: CodeArtifactProps) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-paper">
      <div className="border-b border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
        {language}
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6">
        <code>{code}</code>
      </pre>
    </div>
  );
}
