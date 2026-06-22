import { Badge } from "@/components/ui/badge";
import type { LiteratureRow } from "@/types/research";

interface LiteratureMatrixProps {
  rows: LiteratureRow[];
}

export function LiteratureMatrix({ rows }: LiteratureMatrixProps) {
  return (
    <div className="overflow-x-auto rounded-md border border-border/80 bg-paper quiet-scrollbar">
      <table className="min-w-[760px] border-collapse text-left text-xs">
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th className="w-[45%] border-b border-border px-3 py-2 font-medium">Paper</th>
            <th className="w-[40%] border-b border-border px-3 py-2 font-medium">Direction</th>
            <th className="w-[15%] border-b border-border px-3 py-2 font-medium">Signal</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="align-top hover:bg-accent/25">
              <td className="border-b border-border px-3 py-3">
                <div className="max-w-[360px] text-wrap font-medium leading-5 text-foreground">
                  {row.title}
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span>{row.year}</span>
                  {row.source && <span>{row.source}</span>}
                  {row.importance && (
                    <Badge>{row.importance === "core" ? "core" : "support"}</Badge>
                  )}
                  {typeof row.score === "number" && <span>{row.score.toFixed(1)}</span>}
                </div>
                <div className="mt-2 max-w-[420px] text-wrap leading-5 text-muted-foreground">
                  {row.evidence}
                </div>
              </td>
              <td className="border-b border-border px-3 py-3">
                <div className="font-medium leading-5">{row.direction}</div>
                <div className="mt-2 max-w-[360px] text-wrap leading-5 text-muted-foreground">
                  {row.method}
                </div>
              </td>
              <td className="border-b border-border px-3 py-3">
                <Badge>{row.confidence}</Badge>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td
                colSpan={3}
                className="px-3 py-8 text-center text-sm text-muted-foreground"
              >
                No literature rows available for this run.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
