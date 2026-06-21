import type {
  AgentId,
  AgentStatus,
  Artifact,
  RunSummary,
  ResearchSettings,
  UploadedPdf,
  ThreadMessage
} from "@/types/research";

export interface ChatRequest {
  topic: string;
  settings: ResearchSettings;
  uploads: UploadedPdf[];
}

export type ChatStreamEvent =
  | {
      type: "message.delta";
      messageId: string;
      delta: string;
    }
  | {
      type: "message.done";
      message: ThreadMessage;
    }
  | {
      type: "agent.status";
      agentId: AgentId;
      status: AgentStatus;
      currentTask: string;
      progress: number;
    }
  | {
      type: "artifact.upsert";
      artifact: Artifact;
    }
  | {
      type: "trace.append";
      agentId: AgentId;
      title: string;
      detail: string;
      timestamp?: string;
    }
  | {
      type: "run.completed";
      runName: string;
      workflowEngine: string;
      llmMode: string;
      reportPath: string;
      mindmapPath: string;
      runLogPath: string;
      warnings: string[];
      paperCount: number;
      supportingCount?: number;
      rejectedCount: number;
    }
  | {
      type: "run.error";
      message: string;
    };

export interface ChatTransport {
  sendMessage(request: ChatRequest): AsyncIterable<ChatStreamEvent>;
}

export function toRunSummary(event: Extract<ChatStreamEvent, { type: "run.completed" }>): RunSummary {
  return {
    runName: event.runName,
    workflowEngine: event.workflowEngine,
    llmMode: event.llmMode,
    reportPath: event.reportPath,
    mindmapPath: event.mindmapPath,
    runLogPath: event.runLogPath,
    warnings: event.warnings,
    paperCount: event.paperCount,
    supportingCount: event.supportingCount,
    rejectedCount: event.rejectedCount
  };
}
