import { listThreadProjects } from "@/lib/server/thread-history";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  return Response.json({
    threads: listThreadProjects({
      includeArchived: url.searchParams.get("includeArchived") === "1"
    })
  });
}
