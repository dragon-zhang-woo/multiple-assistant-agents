import fs from "node:fs";
import path from "node:path";
import { getRepoRoot } from "@/lib/server/env";
import type {
  AgentTraceEvent,
  Artifact,
  LiteratureRow,
  ResearchProject,
  RunSummary,
  ThreadMessage
} from "@/types/research";

interface RunLog {
  topic?: string;
  output_dir?: string;
  messages?: Array<{
    speaker?: string;
    content?: string;
    timestamp?: string;
  }>;
  tool_logs?: Array<Record<string, unknown>>;
  warnings?: string[];
  workflow_engine?: string;
  llm_mode?: string;
  run_name?: string;
  report_path?: string;
  mindmap_path?: string;
  run_log_path?: string;
  papers?: Array<Record<string, unknown>>;
  supporting_papers?: Array<Record<string, unknown>>;
  rejected_papers?: Array<Record<string, unknown>>;
  paper_analyses?: Array<Record<string, unknown>>;
  search_diagnostics?: Record<string, unknown>;
}

interface ThreadLocalState {
  archived: Record<string, boolean>;
}

export interface ThreadHistoryDetail {
  project: ResearchProject;
  messages: ThreadMessage[];
  trace: AgentTraceEvent[];
  artifacts: Artifact[];
  runSummary: RunSummary;
  warnings: string[];
}

export function listThreadProjects(options: { includeArchived?: boolean; limit?: number } = {}): ResearchProject[] {
  const state = readThreadState();
  return discoverRunDirs()
    .map((runDir) => buildProjectFromRun(runDir, state))
    .filter((project): project is ResearchProject => Boolean(project))
    .filter((project) => options.includeArchived || project.status !== "archived")
    .sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""))
    .slice(0, options.limit ?? 80);
}

export function getThreadHistory(runName: string): ThreadHistoryDetail | null {
  const safeRunName = sanitizeRunName(runName);
  if (!safeRunName || safeRunName !== runName) {
    return null;
  }
  const runDir = path.join(getRunsRoot(), safeRunName);
  if (!isInside(getRunsRoot(), runDir)) {
    return null;
  }
  const runLog = readRunLog(runDir);
  if (!runLog) {
    return null;
  }

  const state = readThreadState();
  const createdAt = runTimestamp(runDir, runLog);
  const runSummary = buildRunSummary(runDir, runLog);
  const project = projectFromLog(safeRunName, runDir, runLog, createdAt, runSummary, state);
  return {
    project,
    messages: buildMessages(runLog, createdAt),
    trace: buildTrace(runLog),
    artifacts: buildArtifacts(runDir, runLog, safeRunName, createdAt),
    runSummary,
    warnings: collectWarnings(runDir, runLog)
  };
}

export function setThreadArchived(runName: string, archived: boolean) {
  const runDir = safeRunDir(runName);
  if (!runDir || !fs.existsSync(path.join(runDir, "run_log.json"))) {
    return null;
  }
  const state = readThreadState();
  state.archived[path.basename(runDir)] = archived;
  writeThreadState(state);
  const runLog = readRunLog(runDir);
  if (!runLog) {
    return null;
  }
  return projectFromLog(
    path.basename(runDir),
    runDir,
    runLog,
    runTimestamp(runDir, runLog),
    buildRunSummary(runDir, runLog),
    state
  );
}

export function deleteThreadHistory(runName: string) {
  const runDir = safeRunDir(runName);
  if (!runDir || !fs.existsSync(runDir)) {
    return false;
  }
  fs.rmSync(runDir, { recursive: true, force: true });
  const state = readThreadState();
  delete state.archived[path.basename(runDir)];
  writeThreadState(state);
  return true;
}

function buildProjectFromRun(runDir: string, state: ThreadLocalState) {
  const runLog = readRunLog(runDir);
  if (!runLog) {
    return null;
  }
  const runName = path.basename(runDir);
  const createdAt = runTimestamp(runDir, runLog);
  return projectFromLog(
    runName,
    runDir,
    runLog,
    createdAt,
    buildRunSummary(runDir, runLog),
    state
  );
}

function projectFromLog(
  runName: string,
  runDir: string,
  runLog: RunLog,
  createdAt: string,
  summary: RunSummary,
  state: ThreadLocalState
): ResearchProject {
  const topic = cleanText(runLog.topic) || runName;
  const provider = cleanText(runLog.llm_mode) || "unknown";
  return {
    id: `history-${runName}`,
    runName,
    name: topic.slice(0, 44),
    updatedAt: relativeDateLabel(new Date(createdAt)),
    createdAt,
    provider,
    paperCount: summary.paperCount,
    supportingCount: summary.supportingCount,
    description: `${summary.paperCount} papers + ${summary.supportingCount ?? 0} support · ${provider}`,
    status: state.archived[runName] ? "archived" : "active"
  };
}

function buildRunSummary(runDir: string, runLog: RunLog): RunSummary {
  const runName = path.basename(runDir);
  const reportPath = resolveRunFile(runDir, runLog.report_path, "survey.md");
  const mindmapPath = resolveRunFile(runDir, runLog.mindmap_path, "mindmap.md");
  const runLogPath = resolveRunFile(runDir, runLog.run_log_path, "run_log.json");
  return {
    runName,
    workflowEngine: cleanText(runLog.workflow_engine) || "langgraph",
    llmMode: cleanText(runLog.llm_mode) || "unknown",
    reportPath,
    mindmapPath,
    runLogPath,
    warnings: collectWarnings(runDir, runLog),
    paperCount: runLog.papers?.length ?? runLog.paper_analyses?.length ?? 0,
    supportingCount: runLog.supporting_papers?.length ?? 0,
    rejectedCount: runLog.rejected_papers?.length ?? 0
  };
}

function buildMessages(runLog: RunLog, createdAt: string): ThreadMessage[] {
  const topic = cleanText(runLog.topic) || "Restored research run";
  const citations = (runLog.papers ?? [])
    .slice(0, 4)
    .map((paper) => cleanText(paper.title))
    .filter(Boolean);
  return [
    {
      id: `history-user-${hashText(topic)}`,
      role: "user",
      createdAt: timeLabel(createdAt),
      content: topic
    },
    {
      id: `history-assistant-${hashText(topic)}`,
      role: "assistant",
      agentId: "writer",
      createdAt: timeLabel(createdAt),
      content: buildRestoredAssistantMessage(runLog),
      artifactIds: ["survey", "mindmap", "matrix", "run-log"],
      citations
    }
  ];
}

function buildRestoredAssistantMessage(runLog: RunLog) {
  const warningText = runLog.warnings?.length
    ? "\n\n注意：该历史运行包含 warning，可在 Run Log 中查看。"
    : "";
  return (
    `已从本地运行记录恢复《${cleanText(runLog.topic) || "research topic"}》。\n\n` +
    `- 工作流：${cleanText(runLog.workflow_engine) || "langgraph"}\n` +
    `- 模型模式：${cleanText(runLog.llm_mode) || "unknown"}\n` +
    `- 正文论文：${runLog.papers?.length ?? runLog.paper_analyses?.length ?? 0} 篇\n` +
    `- 补充候选：${runLog.supporting_papers?.length ?? 0} 篇\n` +
    `- 过滤候选：${runLog.rejected_papers?.length ?? 0} 篇\n\n` +
    "右侧 Artifacts 可直接查看本次报告、思维导图、文献矩阵和运行日志；打开历史不会重新调用大模型。" +
    warningText
  );
}

function buildTrace(runLog: RunLog): AgentTraceEvent[] {
  return (runLog.messages ?? []).map((message, index) => ({
    id: `history-trace-${index}`,
    agentId: speakerToAgent(cleanText(message.speaker)),
    title: cleanText(message.speaker) || "Workflow event",
    detail: cleanText(message.content),
    status: "done",
    timestamp: timeLabel(cleanText(message.timestamp))
  }));
}

function buildArtifacts(
  runDir: string,
  runLog: RunLog,
  runName: string,
  createdAt: string
): Artifact[] {
  return [
    markdownArtifact("survey", "Survey", "调研报告", runDir, runLog.report_path, "survey.md", runName, createdAt),
    markdownArtifact("mindmap", "Mindmap", "思维导图", runDir, runLog.mindmap_path, "mindmap.md", runName, createdAt),
    matrixArtifact(runLog, runName, createdAt),
    codeArtifact(runDir, runLog.run_log_path, runName, createdAt)
  ];
}

function markdownArtifact(
  id: string,
  title: string,
  summary: string,
  runDir: string,
  rawPath: string | undefined,
  fallbackFile: string,
  runName: string,
  createdAt: string
): Artifact {
  const filePath = resolveRunFile(runDir, rawPath, fallbackFile);
  const content = readText(filePath) || `无法读取 ${fallbackFile}。`;
  return {
    id,
    title,
    kind: "markdown",
    versions: [
      {
        id: runName,
        label: runName,
        createdAt: formatDateTime(createdAt),
        summary,
        content
      }
    ]
  };
}

function matrixArtifact(runLog: RunLog, runName: string, createdAt: string): Artifact {
  const coreRows = (runLog.paper_analyses ?? runLog.papers ?? []).map((paper, index) =>
    paperToRow(paper, `paper-${index + 1}`, "core")
  );
  const supportingRows = (runLog.supporting_papers ?? []).map((paper, index) =>
    paperToRow(paper, `supporting-${index + 1}`, "supporting")
  );
  return {
    id: "matrix",
    title: "Literature Matrix",
    kind: "literature-matrix",
    versions: [
      {
        id: runName,
        label: runName,
        createdAt: formatDateTime(createdAt),
        summary: "代表论文矩阵",
        content: "",
        literature: [...coreRows, ...supportingRows]
      }
    ]
  };
}

function codeArtifact(
  runDir: string,
  rawPath: string | undefined,
  runName: string,
  createdAt: string
): Artifact {
  const filePath = resolveRunFile(runDir, rawPath, "run_log.json");
  return {
    id: "run-log",
    title: "Run Log",
    kind: "code",
    versions: [
      {
        id: runName,
        label: runName,
        createdAt: formatDateTime(createdAt),
        summary: "workflow run_log.json",
        content: readText(filePath) || "{}",
        language: "json"
      }
    ]
  };
}

function paperToRow(
  paper: Record<string, unknown>,
  id: string,
  fallbackImportance: "core" | "supporting"
): LiteratureRow {
  const score = numberValue(paper.relevance_score ?? paper.score);
  return {
    id,
    title: cleanText(paper.title) || "Untitled paper",
    year: cleanText(paper.year) || "n.d.",
    source: cleanText(paper.source) || "unknown",
    importance: cleanText(paper.importance) === "supporting" ? "supporting" : fallbackImportance,
    score,
    direction: cleanText(paper.category) || cleanText(paper.direction) || "未分类",
    method: cleanText(paper.method) || "摘要与元数据分析",
    evidence: cleanText(paper.contribution) || cleanText(paper.summary) || cleanText(paper.abstract) || "暂无摘要。",
    confidence: score >= 6 ? "high" : score >= 3 ? "medium" : "low"
  };
}

function collectWarnings(runDir: string, runLog: RunLog) {
  const warnings = [...(runLog.warnings ?? [])];
  for (const fileName of ["survey.md", "mindmap.md", "run_log.json"]) {
    if (!fs.existsSync(path.join(runDir, fileName))) {
      warnings.push(`Missing ${fileName} in ${path.basename(runDir)}.`);
    }
  }
  return warnings;
}

function discoverRunDirs() {
  const root = getRunsRoot();
  if (!fs.existsSync(root)) {
    return [];
  }
  return fs
    .readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(root, entry.name))
    .filter((dir) => fs.existsSync(path.join(dir, "run_log.json")));
}

function readRunLog(runDir: string): RunLog | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(runDir, "run_log.json"), "utf8")) as RunLog;
  } catch {
    return null;
  }
}

function resolveRunFile(runDir: string, rawPath: string | undefined, fallbackFile: string) {
  const fallback = path.join(runDir, fallbackFile);
  if (!rawPath) {
    return fallback;
  }
  const resolved = path.resolve(rawPath);
  return isInside(runDir, resolved) || resolved === fallback ? resolved : fallback;
}

function runTimestamp(runDir: string, runLog: RunLog) {
  const firstTimestamp = runLog.messages?.find((message) => message.timestamp)?.timestamp;
  if (firstTimestamp) {
    return firstTimestamp;
  }
  return fs.statSync(path.join(runDir, "run_log.json")).mtime.toISOString();
}

function getRunsRoot() {
  return path.join(getRepoRoot(), "runs");
}

function getThreadStatePath() {
  return path.join(getRepoRoot(), "web", ".thread-state.json");
}

function safeRunDir(runName: string) {
  const safeRunName = sanitizeRunName(runName);
  if (!safeRunName || safeRunName !== runName) {
    return null;
  }
  const runDir = path.join(getRunsRoot(), safeRunName);
  return isInside(getRunsRoot(), runDir) ? runDir : null;
}

function readThreadState(): ThreadLocalState {
  try {
    const parsed = JSON.parse(fs.readFileSync(getThreadStatePath(), "utf8")) as Partial<ThreadLocalState>;
    return {
      archived: parsed.archived && typeof parsed.archived === "object" ? parsed.archived : {}
    };
  } catch {
    return { archived: {} };
  }
}

function writeThreadState(state: ThreadLocalState) {
  fs.writeFileSync(getThreadStatePath(), JSON.stringify(state, null, 2), "utf8");
}

function isInside(root: string, target: string) {
  const relative = path.relative(path.resolve(root), path.resolve(target));
  return Boolean(relative) && !relative.startsWith("..") && !path.isAbsolute(relative);
}

function sanitizeRunName(value: string) {
  return value.replace(/[^A-Za-z0-9_.-]/g, "");
}

function speakerToAgent(speaker: string): AgentTraceEvent["agentId"] {
  const normalized = speaker.toLowerCase();
  if (normalized.includes("manager") || normalized.includes("planner")) {
    return "planner";
  }
  if (normalized.includes("search") || normalized.includes("scholar")) {
    return "scholar";
  }
  if (normalized.includes("reading") || normalized.includes("reader")) {
    return "reader";
  }
  if (normalized.includes("critic")) {
    return "critic";
  }
  return "writer";
}

function readText(filePath: string) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return "";
  }
}

function cleanText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function hashText(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16);
}

function timeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "--:--";
  }
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function relativeDateLabel(date: Date) {
  if (Number.isNaN(date.getTime())) {
    return "saved";
  }
  const diffMs = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diffMs < minute) {
    return "just now";
  }
  if (diffMs < hour) {
    return `${Math.max(1, Math.floor(diffMs / minute))} min ago`;
  }
  if (diffMs < day) {
    return `${Math.floor(diffMs / hour)} h ago`;
  }
  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit"
  });
}
