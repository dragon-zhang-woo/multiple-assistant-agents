"use client";

import { useMemo, useState } from "react";
import { mockResearchSession } from "@/lib/mock/research-session";
import type {
  AgentProfile,
  AgentStatus,
  Artifact,
  ResearchProject,
  ThreadMessage
} from "@/types/research";

export function useResearchThread() {
  const [messages, setMessages] = useState<ThreadMessage[]>(
    mockResearchSession.messages
  );
  const [agents, setAgents] = useState<AgentProfile[]>(
    mockResearchSession.agents
  );
  const [activeArtifactId, setActiveArtifactId] = useState(
    mockResearchSession.artifacts[0]?.id ?? ""
  );
  const [artifactCollapsed, setArtifactCollapsed] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeProjectId, setActiveProjectId] = useState(
    mockResearchSession.projects[0]?.id ?? ""
  );

  const artifacts = mockResearchSession.artifacts;
  const activeArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.id === activeArtifactId) ?? artifacts[0],
    [activeArtifactId, artifacts]
  );
  const activeProject = useMemo(
    () =>
      mockResearchSession.projects.find((project) => project.id === activeProjectId) ??
      mockResearchSession.projects[0],
    [activeProjectId]
  );

  function setAgentStatus(name: string, status: AgentStatus, progress: number) {
    setAgents((current) =>
      current.map((agent) =>
        agent.name === name
          ? {
              ...agent,
              status,
              progress,
              currentTask:
                status === "done" ? "已同步到当前 thread" : agent.currentTask
            }
          : agent
      )
    );
  }

  function sendMessage(content: string) {
    const trimmed = content.trim();
    if (!trimmed) {
      return;
    }
    const now = new Date();
    const userMessage: ThreadMessage = {
      id: `u-${now.getTime()}`,
      role: "user",
      createdAt: now.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit"
      }),
      content: trimmed
    };
    const assistantMessage: ThreadMessage = {
      id: `a-${now.getTime()}`,
      role: "assistant",
      agentId: "writer",
      createdAt: now.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit"
      }),
      artifactIds: ["survey", "matrix"],
      citations: ["Agent Memory", "Long-term Memory", "Reflection"],
      content:
        "收到。我会先把这个请求作为新的研究子任务，沿用 Planner -> Scholar -> Reader -> Critic -> Writer 的流程。当前版本仍是 mock transport；接入 `/api/chat` 后，这里会替换为流式增量消息和 Agent 状态事件。"
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setAgentStatus("Writer", "working", 74);
    setActiveArtifactId("survey");
    setArtifactCollapsed(false);
    window.setTimeout(() => {
      setAgentStatus("Writer", "done", 100);
    }, 900);
  }

  return {
    projects: mockResearchSession.projects as ResearchProject[],
    activeProject,
    setActiveProjectId,
    agents,
    messages,
    trace: mockResearchSession.trace,
    artifacts: artifacts as Artifact[],
    activeArtifact,
    activeArtifactId,
    setActiveArtifactId,
    artifactCollapsed,
    setArtifactCollapsed,
    traceOpen,
    setTraceOpen,
    sendMessage
  };
}
