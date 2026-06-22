import {
  deleteThreadHistory,
  getThreadHistory,
  setThreadArchived
} from "@/lib/server/thread-history";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{
    runName: string;
  }>;
}

export async function GET(_request: Request, context: RouteContext) {
  const { runName } = await context.params;
  const thread = getThreadHistory(runName);
  if (!thread) {
    return Response.json({ error: "Thread not found." }, { status: 404 });
  }
  return Response.json(thread);
}

export async function PATCH(request: Request, context: RouteContext) {
  const { runName } = await context.params;
  const body = (await request.json().catch(() => ({}))) as {
    status?: "active" | "archived";
  };
  if (body.status !== "active" && body.status !== "archived") {
    return Response.json({ error: "Unsupported thread status." }, { status: 400 });
  }
  const project = setThreadArchived(runName, body.status === "archived");
  if (!project) {
    return Response.json({ error: "Thread not found." }, { status: 404 });
  }
  return Response.json({ project });
}

export async function DELETE(_request: Request, context: RouteContext) {
  const { runName } = await context.params;
  if (!deleteThreadHistory(runName)) {
    return Response.json({ error: "Thread not found." }, { status: 404 });
  }
  return Response.json({ ok: true });
}
