import { cn } from "@/lib/utils";

interface MarkdownArtifactProps {
  content: string;
}

export function MarkdownArtifact({ content }: MarkdownArtifactProps) {
  const lines = content.split("\n");
  return (
    <article className="rounded-md border border-border bg-paper p-5 paper-prose">
      {lines.map((line, index) => {
        if (line.startsWith("## ")) {
          return (
            <h2 key={index} className="mb-2 mt-5 text-base font-semibold first:mt-0">
              {line.replace(/^##\s*/, "")}
            </h2>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <div key={index} className="ml-3 flex gap-2 text-sm leading-7">
              <span className="mt-[0.65em] h-1 w-1 rounded-full bg-muted-foreground" />
              <span>{line.replace(/^-\s*/, "")}</span>
            </div>
          );
        }
        if (!line.trim()) {
          return <div key={index} className="h-3" />;
        }
        return (
          <p key={index} className={cn("text-sm leading-7 text-foreground")}>
            {line}
          </p>
        );
      })}
    </article>
  );
}
