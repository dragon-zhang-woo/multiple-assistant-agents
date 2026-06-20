export type AgentId = "planner" | "scholar" | "reader" | "critic" | "writer";

export type AgentStatus = "idle" | "queued" | "working" | "reviewing" | "done";

export type MessageRole = "user" | "assistant";

export type ArtifactKind = "markdown" | "literature-matrix" | "code";

export type NonEmptyArray<T> = [T, ...T[]];

export interface AgentProfile {
  id: AgentId;
  name: string;
  role: string;
  status: AgentStatus;
  progress: number;
  currentTask: string;
}

export interface AgentTraceEvent {
  id: string;
  agentId: AgentId;
  title: string;
  detail: string;
  status: AgentStatus;
  timestamp: string;
}

export interface LiteratureRow {
  id: string;
  title: string;
  year: string;
  direction: string;
  method: string;
  evidence: string;
  confidence: "high" | "medium" | "low";
}

export interface ArtifactVersion {
  id: string;
  label: string;
  createdAt: string;
  summary: string;
  content: string;
  literature?: LiteratureRow[];
  language?: string;
}

export interface Artifact {
  id: string;
  title: string;
  kind: ArtifactKind;
  versions: NonEmptyArray<ArtifactVersion>;
}

export interface ThreadMessage {
  id: string;
  role: MessageRole;
  createdAt: string;
  content: string;
  agentId?: AgentId;
  artifactIds?: string[];
  citations?: string[];
}

export interface ResearchProject {
  id: string;
  name: string;
  updatedAt: string;
  description: string;
  status: "active" | "draft" | "archived";
}

export interface ResearchSession {
  projects: NonEmptyArray<ResearchProject>;
  agents: NonEmptyArray<AgentProfile>;
  messages: ThreadMessage[];
  trace: AgentTraceEvent[];
  artifacts: NonEmptyArray<Artifact>;
}
