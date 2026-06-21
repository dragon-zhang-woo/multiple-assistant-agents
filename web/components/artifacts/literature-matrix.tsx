import { Badge } from "@/components/ui/badge";
import type { LiteratureRow } from "@/types/research";

interface LiteratureMatrixProps {
  rows: LiteratureRow[];
}

export function LiteratureMatrix({ rows }: LiteratureMatrixProps) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-paper">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="bg-muted text-muted-foreground">
          <tr>
            <th className="border-b border-border px-3 py-2 font-medium">Paper</th>
            <th className="border-b border-border px-3 py-2 font-medium">Direction</th>
            <th className="border-b border-border px-3 py-2 font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="align-top">
              <td className="border-b border-border px-3 py-3">
                <div className="font-medium text-foreground">{row.title}</div>
                <div className="mt-1 flex flex-wrap items-center gap-1 text-muted-foreground">
                  <span>{row.year}</span>
                  {row.source && <span>· {row.source}</span>}
                  {row.importance && (
                    <Badge>{row.importance === "core" ? "core" : "support"}</Badge>
                  )}
                </div>
                <div className="mt-2 leading-5 text-muted-foreground">
                  {row.evidence}
                </div>
              </td>
              <td className="border-b border-border px-3 py-3">
                <div className="font-medium">{row.direction}</div>
                <div className="mt-2 leading-5 text-muted-foreground">
                  {row.method}
                </div>
              </td>
              <td className="border-b border-border px-3 py-3">
                <Badge>{row.confidence}</Badge>
                {typeof row.score === "number" && (
                  <div className="mt-2 text-[11px] text-muted-foreground">
                    {row.score.toFixed(2)}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
