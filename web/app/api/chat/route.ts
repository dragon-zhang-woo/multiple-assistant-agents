import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { getRepoRoot, getWebRoot } from "@/lib/server/env";
import {
  buildChildEnv,
  normalizeProvider,
  providerIsConfigured,
  providerMissingMessage
} from "@/lib/server/providers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface ChatRequestBody {
  topic?: string;
  provider?: string;
  model?: string;
  maxPapers?: number;
  candidatePool?: number;
  minRelevance?: number;
  sort?: "relevance" | "submittedDate";
  mockMode?: "auto" | "always" | "never";
  uploads?: Array<{ path?: string }>;
}

const encoder = new TextEncoder();

export async function POST(request: Request) {
  const body = (await request.json()) as ChatRequestBody;
  const topic = body.topic?.trim();
  const provider = normalizeProvider(body.provider);

  if (!topic) {
    return sseFromEvents([
      {
        type: "run.error",
        message: "请输入科研问题或调研主题。"
      }
    ]);
  }

  if (!providerIsConfigured(provider)) {
    return sseFromEvents([
      {
        type: "run.error",
        message: providerMissingMessage(provider)
      }
    ]);
  }

  const pdfPaths = resolvePdfPaths(body.uploads ?? []);
  const payload = {
    topic,
    provider,
    model: body.model?.trim() ?? "",
    maxPapers: clampNumber(body.maxPapers, 1, 12, 5),
    candidatePool: clampNumber(body.candidatePool, 0, 80, 25),
    minRelevance: clampNumber(body.minRelevance, 0, 12, 3),
    sort: body.sort === "submittedDate" ? "submittedDate" : "relevance",
    mockMode: body.mockMode ?? "auto",
    pdfPaths,
    runName: `web-${Date.now()}`
  };

  return pythonWorkflowStream(payload, provider, body.model);
}

function pythonWorkflowStream(
  payload: Record<string, unknown>,
  provider: ReturnType<typeof normalizeProvider>,
  model?: string
) {
  const repoRoot = getRepoRoot();
  const python = resolvePython(repoRoot);
  const runner = path.join(repoRoot, "code", "web_runner.py");
  let child: ReturnType<typeof spawn> | undefined;
  let sawTerminalEvent = false;

  const stream = new ReadableStream({
    start(controller) {
      child = spawn(python, [runner], {
        cwd: repoRoot,
        env: buildChildEnv(model, provider),
        stdio: ["pipe", "pipe", "pipe"]
      });

      let stdoutBuffer = "";
      let stderrBuffer = "";

      child.stdout?.on("data", (chunk: Buffer) => {
        stdoutBuffer += chunk.toString("utf8");
        const lines = stdoutBuffer.split(/\r?\n/);
        stdoutBuffer = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            continue;
          }
          try {
            const event = JSON.parse(trimmed);
            if (event.type === "run.completed" || event.type === "run.error") {
              sawTerminalEvent = true;
            }
            enqueueSse(controller, event);
          } catch {
            enqueueSse(controller, {
              type: "trace.append",
              agentId: "planner",
              title: "Runner output",
              detail: trimmed.slice(0, 400)
            });
          }
        }
      });

      child.stderr?.on("data", (chunk: Buffer) => {
        stderrBuffer += chunk.toString("utf8");
      });

      child.on("error", (error) => {
        sawTerminalEvent = true;
        enqueueSse(controller, {
          type: "run.error",
          message: sanitizeError(error.message)
        });
        controller.close();
      });

      child.on("close", (code) => {
        if (stdoutBuffer.trim()) {
          try {
            enqueueSse(controller, JSON.parse(stdoutBuffer.trim()));
          } catch {
            enqueueSse(controller, {
              type: "trace.append",
              agentId: "planner",
              title: "Runner output",
              detail: stdoutBuffer.trim().slice(0, 400)
            });
          }
        }
        if (code !== 0 && !sawTerminalEvent) {
          enqueueSse(controller, {
            type: "run.error",
            message:
              sanitizeError(stderrBuffer.trim()) ||
              `Python workflow exited with code ${code}.`
          });
        }
        controller.close();
      });

      child.stdin?.end(JSON.stringify(payload));
    },
    cancel() {
      child?.kill();
    }
  });

  return sseResponse(stream);
}

function sseFromEvents(events: Array<Record<string, unknown>>) {
  const stream = new ReadableStream({
    start(controller) {
      for (const event of events) {
        enqueueSse(controller, event);
      }
      controller.close();
    }
  });
  return sseResponse(stream);
}

function sseResponse(stream: ReadableStream) {
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}

function enqueueSse(
  controller: ReadableStreamDefaultController,
  event: Record<string, unknown>
) {
  controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
}

function resolvePython(repoRoot: string) {
  const localPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(localPython)) {
    return localPython;
  }
  return process.env.PYTHON || "python";
}

function resolvePdfPaths(uploads: Array<{ path?: string }>) {
  const uploadRoot = path.resolve(getWebRoot(), ".uploads");
  return uploads
    .map((item) => item.path ?? "")
    .map((item) => path.resolve(item))
    .filter((item) => item.startsWith(uploadRoot + path.sep))
    .filter((item) => fs.existsSync(item));
}

function clampNumber(
  value: number | undefined,
  min: number,
  max: number,
  fallback: number
) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, value));
}

function sanitizeError(message: string) {
  return message.replace(/(sk-|ds-)[A-Za-z0-9_-]+/g, "[redacted]");
}
