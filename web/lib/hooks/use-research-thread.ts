"use client";

import { useEffect, useMemo, useState } from "react";
import { toRunSummary, type ChatStreamEvent } from "@/lib/chat/events";
import { SseChatTransport } from "@/lib/chat/sse-transport";
import type {
  AgentId,
  AgentProfile,
  AgentStatus,
  Artifact,
  NonEmptyArray,
  ProviderId,
  ProviderInfo,
  ProvidersResponse,
  ResearchProject,
  ResearchSettings,
  RunSummary,
  ThreadMessage,
  UploadedPdf
} from "@/types/research";

const initialAgents: NonEmptyArray<AgentProfile> = [
  {
    id: "planner",
    name: "Planner",
    role: "任务拆解与流程调度",
    status: "idle",
    progress: 0,
    currentTask: "等待研究问题"
  },
  {
    id: "scholar",
    name: "Scholar",
    role: "arXiv 检索与候选过滤",
    status: "idle",
    progress: 0,
    currentTask: "等待检索"
  },
  {
    id: "reader",
    name: "Reader",
    role: "摘要与 PDF 阅读",
    status: "idle",
    progress: 0,
    currentTask: "等待阅读"
  },
  {
    id: "critic",
    name: "Critic",
    role: "Reflection 与风险分析",
    status: "idle",
    progress: 0,
    currentTask: "等待反思"
  },
  {
    id: "writer",
    name: "Writer",
    role: "报告与 Artifact 汇总",
    status: "idle",
    progress: 0,
    currentTask: "等待写作"
  }
];

const initialSettings: ResearchSettings = {
  provider: "mock",
  model: "deterministic-mock",
  maxPapers: 5,
  candidatePool: 25,
  minRelevance: 3,
  sort: "relevance",
  mockMode: "always"
};

const defaultProject: ResearchProject = {
  id: "new-run",
  name: "New research run",
  updatedAt: "ready",
  description: "输入主题后启动真实多 Agent 科研流程",
  status: "active"
};

export function useResearchThread() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [projects, setProjects] = useState<ResearchProject[]>([defaultProject]);
  const [activeProjectId, setActiveProjectId] = useState(defaultProject.id);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>(initialAgents);
  const [trace, setTrace] = useState<ChatTrace[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeArtifactId, setActiveArtifactId] = useState("");
  const [artifactCollapsed, setArtifactCollapsed] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([
    {
      id: "mock",
      label: "Mock",
      configured: true,
      defaultModel: "deterministic-mock",
      baseUrl: "local",
      note: "No API key required"
    }
  ]);
  const [settings, setSettings] = useState<ResearchSettings>(initialSettings);
  const [uploads, setUploads] = useState<UploadedPdf[]>([]);
  const [uploadError, setUploadError] = useState("");
  const [runError, setRunError] = useState("");
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    const storedTheme = window.localStorage.getItem("research-theme");
    if (storedTheme === "dark" || storedTheme === "light") {
      setTheme(storedTheme);
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("research-theme", theme);
  }, [theme]);

  useEffect(() => {
    let mounted = true;
    fetch("/api/providers", { cache: "no-store" })
      .then((response) => response.json() as Promise<ProvidersResponse>)
      .then((data) => {
        if (!mounted) {
          return;
        }
        setProviders(data.providers);
        const provider = data.defaultProvider;
        const selected = data.providers.find((item) => item.id === provider);
        setSettings((current) => ({
          ...current,
          provider,
          model: selected?.defaultModel ?? current.model,
          mockMode: provider === "mock" ? "always" : "never"
        }));
      })
      .catch(() => {
        setRunError("无法读取服务端 provider 配置，已保留 mock 模式。");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const activeArtifact = useMemo(
    () =>
      artifacts.find((artifact) => artifact.id === activeArtifactId) ??
      artifacts[0],
    [activeArtifactId, artifacts]
  );
  const activeProject = useMemo(
    () =>
      projects.find((project) => project.id === activeProjectId) ??
      projects[0] ??
      defaultProject,
    [activeProjectId, projects]
  );

  function updateSettings(next: Partial<ResearchSettings>) {
    setSettings((current) => ({
      ...current,
      ...next
    }));
  }

  function selectProvider(provider: ProviderId) {
    const selected = providers.find((item) => item.id === provider);
    setSettings((current) => ({
      ...current,
      provider,
      model:
        provider === "mock"
          ? "deterministic-mock"
          : selected?.defaultModel ?? current.model,
      mockMode: provider === "mock" ? "always" : "never"
    }));
  }

  function toggleTheme() {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }

  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) {
      return;
    }
    setUploadError("");
    const formData = new FormData();
    for (const file of list) {
      formData.append("files", file);
    }
    const response = await fetch("/api/uploads", {
      method: "POST",
      body: formData
    });
    const data = (await response.json()) as {
      files?: UploadedPdf[];
      error?: string;
    };
    if (!response.ok) {
      setUploadError(data.error ?? "PDF 上传失败。");
      return;
    }
    setUploads((current) => [...current, ...(data.files ?? [])]);
  }

  function removeUpload(id: string) {
    setUploads((current) => current.filter((file) => file.id !== id));
  }

  async function sendMessage(content: string) {
    const topic = content.trim();
    if (!topic || isRunning) {
      return;
    }
    const createdAt = timeLabel();
    setMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        createdAt,
        content: topic
      }
    ]);
    setRunError("");
    setRunSummary(null);
    setTrace([]);
    setArtifacts([]);
    setActiveArtifactId("");
    setAgents(resetAgents("queued"));
    setIsRunning(true);
    setTraceOpen(true);

    const transport = new SseChatTransport();
    try {
      for await (const event of transport.sendMessage({
        topic,
        settings,
        uploads
      })) {
        handleStreamEvent(event, topic);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "运行失败。";
      handleRunError(message);
    } finally {
      setIsRunning(false);
    }
  }

  function handleStreamEvent(event: ChatStreamEvent, topic: string) {
    if (event.type === "agent.status") {
      setAgents((current) =>
        current.map((agent) =>
          agent.id === event.agentId
            ? {
                ...agent,
                status: event.status,
                progress: event.progress,
                currentTask: event.currentTask
              }
            : agent
        )
      );
      return;
    }

    if (event.type === "trace.append") {
      setTrace((current) => [
        ...current,
        {
          id: `trace-${Date.now()}-${current.length}`,
          agentId: event.agentId,
          title: event.title,
          detail: event.detail,
          status: "done",
          timestamp: event.timestamp
            ? new Date(event.timestamp).toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit"
              })
            : timeLabel()
        }
      ]);
      return;
    }

    if (event.type === "artifact.upsert") {
      upsertArtifact(event.artifact);
      setActiveArtifactId((current) => current || event.artifact.id);
      setArtifactCollapsed(false);
      return;
    }

    if (event.type === "message.delta") {
      appendAssistantDelta(event.messageId, event.delta);
      return;
    }

    if (event.type === "message.done") {
      setMessages((current) => [...current, event.message]);
      return;
    }

    if (event.type === "run.completed") {
      const summary = toRunSummary(event);
      setRunSummary(summary);
      setProjects((current) => [
        {
          id: summary.runName,
          name: topic.slice(0, 34) || "Research run",
          updatedAt: "just now",
          description: `${summary.paperCount} papers · ${summary.llmMode}`,
          status: "active"
        },
        ...current.filter((project) => project.id !== "new-run").slice(0, 7)
      ]);
      setActiveProjectId(summary.runName);
      return;
    }

    if (event.type === "run.error") {
      handleRunError(event.message);
    }
  }

  function appendAssistantDelta(messageId: string, delta: string) {
    setMessages((current) => {
      const existing = current.find((message) => message.id === messageId);
      if (!existing) {
        return [
          ...current,
          {
            id: messageId,
            role: "assistant",
            agentId: "writer",
            createdAt: timeLabel(),
            content: delta
          }
        ];
      }
      return current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content: `${message.content}${delta}`
            }
          : message
      );
    });
  }

  function upsertArtifact(artifact: Artifact) {
    setArtifacts((current) => {
      const existing = current.find((item) => item.id === artifact.id);
      if (!existing) {
        return [...current, artifact];
      }
      const versions = [
        ...existing.versions,
        ...artifact.versions.filter(
          (version) =>
            !existing.versions.some((item) => item.id === version.id)
        )
      ] as NonEmptyArray<Artifact["versions"][number]>;
      return current.map((item) =>
        item.id === artifact.id
          ? {
              ...artifact,
              versions
            }
          : item
      );
    });
  }

  function handleRunError(message: string) {
    setRunError(message);
    setAgents((current) =>
      current.map((agent) =>
        agent.status === "working" || agent.status === "queued"
          ? {
              ...agent,
              status: "error" as AgentStatus,
              currentTask: "运行中断"
            }
          : agent
      )
    );
    setMessages((current) => [
      ...current,
      {
        id: `error-${Date.now()}`,
        role: "assistant",
        agentId: "writer",
        createdAt: timeLabel(),
        content: `运行失败：${message}`
      }
    ]);
  }

  return {
    projects,
    activeProject,
    setActiveProjectId,
    agents,
    messages,
    trace,
    artifacts,
    activeArtifact,
    activeArtifactId,
    setActiveArtifactId,
    artifactCollapsed,
    setArtifactCollapsed,
    traceOpen,
    setTraceOpen,
    providers,
    settings,
    updateSettings,
    selectProvider,
    uploads,
    uploadFiles,
    removeUpload,
    uploadError,
    runError,
    runSummary,
    isRunning,
    theme,
    toggleTheme,
    sendMessage
  };
}

type ChatTrace = {
  id: string;
  agentId: AgentId;
  title: string;
  detail: string;
  status: AgentStatus;
  timestamp: string;
};

function resetAgents(status: AgentStatus) {
  return initialAgents.map((agent) => ({
    ...agent,
    status,
    progress: 0,
    currentTask: "Waiting for workflow handoff"
  }));
}

function timeLabel() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}
