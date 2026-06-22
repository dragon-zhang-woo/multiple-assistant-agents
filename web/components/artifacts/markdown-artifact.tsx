import { HorizontalScrollFrame } from "@/components/artifacts/horizontal-scroll-frame";
import { cn } from "@/lib/utils";

interface MarkdownArtifactProps {
  content: string;
}

type Block =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "list"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "table"; rows: string[][] }
  | { type: "code"; text: string };

export function MarkdownArtifact({ content }: MarkdownArtifactProps) {
  const blocks = parseMarkdown(content || "Artifact is empty.");
  return (
    <article className="overflow-hidden rounded-md border border-border/80 bg-paper p-5 paper-prose">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = block.level === 1 ? "h1" : block.level === 2 ? "h2" : "h3";
          return (
            <Tag
              key={index}
              className={cn(
                "font-semibold",
                block.level === 1 && "mb-3 text-lg",
                block.level === 2 && "mb-2 mt-5 text-base first:mt-0",
                block.level === 3 && "mb-2 mt-4 text-sm"
              )}
            >
              {block.text}
            </Tag>
          );
        }
        if (block.type === "list") {
          return (
            <div key={index} className="ml-3 flex gap-2 break-words text-sm leading-7">
              <span className="mt-[0.65em] h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
              <span>{block.text}</span>
            </div>
          );
        }
        if (block.type === "table") {
          return <MarkdownTable key={index} rows={block.rows} />;
        }
        if (block.type === "code") {
          return (
            <pre
              key={index}
              className="my-3 overflow-x-auto rounded-md border border-border bg-background p-3 text-xs leading-6"
            >
              <code>{block.text}</code>
            </pre>
          );
        }
        return (
          <p key={index} className="break-words text-sm leading-7 text-foreground">
            {block.text}
          </p>
        );
      })}
    </article>
  );
}

function MarkdownTable({ rows }: { rows: string[][] }) {
  const [header, ...body] = rows;
  return (
    <HorizontalScrollFrame className="my-3 rounded-md border border-border/80">
      <table className="min-w-[720px] border-collapse text-left text-xs">
        {header && (
          <thead className="bg-background">
            <tr>
              {header.map((cell, index) => (
                <th key={index} className="border-b border-border px-2 py-2 font-medium">
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-border last:border-b-0">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="align-top px-2 py-2 leading-5">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </HorizontalScrollFrame>
  );
}

function parseMarkdown(content: string) {
  const lines = content.split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", text: code.join("\n") });
      index += 1;
      continue;
    }
    if (line.startsWith("|")) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].startsWith("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "table", rows: parseTable(tableLines) });
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push({ type: "heading", level: 1, text: line.replace(/^#\s*/, "") });
      index += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ type: "heading", level: 2, text: line.replace(/^##\s*/, "") });
      index += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push({ type: "heading", level: 3, text: line.replace(/^###\s*/, "") });
      index += 1;
      continue;
    }
    if (line.startsWith("- ")) {
      blocks.push({ type: "list", text: line.replace(/^-\s*/, "") });
      index += 1;
      continue;
    }
    blocks.push({ type: "paragraph", text: line });
    index += 1;
  }

  return blocks;
}

function parseTable(lines: string[]) {
  return lines
    .filter((line) => !/^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line))
    .map((line) =>
      line
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => cell.trim())
    );
}
