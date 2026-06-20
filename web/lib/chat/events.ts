import type {
  AgentId,
  AgentStatus,
  Artifact,
  ThreadMessage
} from "@/types/research";

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
    };

export interface ChatTransport {
  sendMessage(input: string): AsyncIterable<ChatStreamEvent>;
}
