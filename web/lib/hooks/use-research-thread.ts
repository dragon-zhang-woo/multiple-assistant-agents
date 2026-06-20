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
  id: "thread-initial",
  name: "New research run",
  updatedAt: "ready",
  description: "输入主题后启动真实多 Agent 科研流程",
  status: "active"
};

export function useResearchThread() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [sessions, setSessions] = useState<Record<string, ThreadSession>>(() => ({
    [defaultProject.id]: createSession(defaultProject)
  }));
  const [projectOrder, setProjectOrder] = useState<string[]>([defaultProject.id]);
  const [activeProjectId, setActiveProjectId] = useState(defaultProject.id);
  const [searchQuery, setSearchQuery] = useState("");
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
  const [isRunningByThread, setIsRunningByThread] = useState<Record<string, boolean>>({});

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
        updateSession(activeProjectId, (session) => ({
          ...session,
          runError: "无法读取服务端 provider 配置，已保留 mock 模式。"
        }));
      });
    return () => {
      mounted = false;
    };
  }, [activeProjectId]);

  const projects = useMemo(
    () => projectOrder.map((id) => sessions[id]?.project).filter(Boolean),
    [projectOrder, sessions]
  );
  const filteredProjects = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return projects;
    }
    return projects.filter((project) => {
      const haystack = `${project.name} ${project.description} ${project.updatedAt}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [projects, searchQuery]);
  const activeSession = sessions[activeProjectId] ?? createSession(defaultProject);
  const activeProject = activeSession.project;
  const activeArtifact = useMemo(
    () =>
      activeSession.artifacts.find(
        (artifact) => artifact.id === activeSession.activeArtifactId
      ) ?? activeSession.artifacts[0],
    [activeSession.activeArtifactId, activeSession.artifacts]
  );
  const isRunning = Boolean(isRunningByThread[activeProjectId]);

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

  function createNewThread() {
    const id = `thread-${Date.now()}`;
    const project: ResearchProject = {
      id,
      name: "New research run",
      updatedAt: "ready",
      description: "输入主题后启动真实多 Agent 科研流程",
      status: "active"
    };
    setSessions((current) => ({
      ...current,
      [id]: createSession(project)
    }));
    setProjectOrder((current) => [id, ...current]);
    setActiveProjectId(id);
    setTraceOpen(false);
    setArtifactCollapsed(false);
  }

  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) {
      return;
    }
    const threadId = activeProjectId;
    updateSession(threadId, (session) => ({ ...session, uploadError: "" }));
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
      updateSession(threadId, (session) => ({
        ...session,
        uploadError: data.error ?? "PDF 上传失败。"
      }));
      return;
    }
    updateSession(threadId, (session) => ({
      ...session,
      uploads: [...session.uploads, ...(data.files ?? [])]
    }));
  }

  function removeUpload(id: string) {
    updateSession(activeProjectId, (session) => ({
      ...session,
      uploads: session.uploads.filter((file) => file.id !== id)
    }));
  }

  async function sendMessage(content: string) {
    const topic = content.trim();
    const threadId = activeProjectId;
    if (!topic || isRunningByThread[threadId]) {
      return;
    }
    const session = sessions[threadId];
    if (!session) {
      return;
    }

    updateSession(threadId, (current) => ({
      ...current,
      project: {
        ...current.project,
        name: topic.slice(0, 34) || "Research run",
        description: "Running multi-agent workflow",
        updatedAt: "running"
      },
      messages: [
        ...current.messages,
        {
          id: `user-${Date.now()}`,
          role: "user",
          createdAt: timeLabel(),
          content: topic
        }
      ],
      agents: resetAgents("queued"),
      trace: [],
      artifacts: [],
      activeArtifactId: "",
      runError: "",
      runSummary: null
    }));
    setProjectOrder((current) => [threadId, ...current.filter((id) => id !== threadId)]);
    setIsRunningByThread((current) => ({ ...current, [threadId]: true }));
    setTraceOpen(true);

    const transport = new SseChatTransport();
    try {
      for await (const event of transport.sendMessage({
        topic,
        settings,
        uploads: session.uploads
      })) {
        handleStreamEvent(threadId, event, topic);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "运行失败。";
      handleRunError(threadId, message);
    } finally {
      setIsRunningByThread((current) => ({ ...current, [threadId]: false }));
    }
  }

  function handleStreamEvent(
    threadId: string,
    event: ChatStreamEvent,
    topic: string
  ) {
    if (event.type === "agent.status") {
      updateSession(threadId, (session) => ({
        ...session,
        agents: session.agents.map((agent) =>
          agent.id === event.agentId
            ? {
                ...agent,
                status: event.status,
                progress: event.progress,
                currentTask: event.currentTask
              }
            : agent
        )
      }));
      return;
    }

    if (event.type === "trace.append") {
      updateSession(threadId, (session) => ({
        ...session,
        trace: [
          ...session.trace,
          {
            id: `trace-${Date.now()}-${session.trace.length}`,
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
        ]
      }));
      return;
    }

    if (event.type === "artifact.upsert") {
      updateSession(threadId, (session) => ({
        ...session,
        artifacts: upsertArtifact(session.artifacts, event.artifact),
        activeArtifactId: session.activeArtifactId || event.artifact.id
      }));
      setArtifactCollapsed(false);
      return;
    }

    if (event.type === "message.delta") {
      updateSession(threadId, (session) => ({
        ...session,
        messages: appendAssistantDelta(
          session.messages,
          event.messageId,
          event.delta
        )
      }));
      return;
    }

    if (event.type === "message.done") {
      updateSession(threadId, (session) => ({
        ...session,
        messages: [...session.messages, event.message]
      }));
      return;
    }

    if (event.type === "run.completed") {
      const summary = toRunSummary(event);
      updateSession(threadId, (session) => ({
        ...session,
        runSummary: summary,
        project: {
          ...session.project,
          name: topic.slice(0, 34) || "Research run",
          updatedAt: "just now",
          description: `${summary.paperCount} papers · ${summary.llmMode}`
        }
      }));
      setProjectOrder((current) => [threadId, ...current.filter((id) => id !== threadId)]);
      return;
    }

    if (event.type === "run.error") {
      handleRunError(threadId, event.message);
    }
  }

  function handleRunError(threadId: string, message: string) {
    updateSession(threadId, (session) => ({
      ...session,
      runError: message,
      agents: session.agents.map((agent) =>
        agent.status === "working" || agent.status === "queued"
          ? {
              ...agent,
              status: "error" as AgentStatus,
              currentTask: "运行中断"
            }
          : agent
      ),
      messages: [
        ...session.messages,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          agentId: "writer",
          createdAt: timeLabel(),
          content: `运行失败：${message}`
        }
      ]
    }));
  }

  function updateSession(
    threadId: string,
    updater: (session: ThreadSession) => ThreadSession
  ) {
    setSessions((current) => {
      const session = current[threadId];
      if (!session) {
        return current;
      }
      return {
        ...current,
        [threadId]: updater(session)
      };
    });
  }

  return {
    projects: filteredProjects,
    activeProject,
    activeProjectId,
    setActiveProjectId,
    createNewThread,
    searchQuery,
    setSearchQuery,
    agents: activeSession.agents,
    messages: activeSession.messages,
    trace: activeSession.trace,
    artifacts: activeSession.artifacts,
    activeArtifact,
    activeArtifactId: activeSession.activeArtifactId,
    setActiveArtifactId: (artifactId: string) =>
      updateSession(activeProjectId, (session) => ({
        ...session,
        activeArtifactId: artifactId
      })),
    artifactCollapsed,
    setArtifactCollapsed,
    traceOpen,
    setTraceOpen,
    providers,
    settings,
    updateSettings,
    selectProvider,
    uploads: activeSession.uploads,
    uploadFiles,
    removeUpload,
    uploadError: activeSession.uploadError,
    runError: activeSession.runError,
    runSummary: activeSession.runSummary,
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

interface ThreadSession {
  project: ResearchProject;
  messages: ThreadMessage[];
  agents: AgentProfile[];
  trace: ChatTrace[];
  artifacts: Artifact[];
  activeArtifactId: string;
  uploads: UploadedPdf[];
  uploadError: string;
  runError: string;
  runSummary: RunSummary | null;
}

function createSession(project: ResearchProject): ThreadSession {
  return {
    project,
    messages: [],
    agents: initialAgents,
    trace: [],
    artifacts: [],
    activeArtifactId: "",
    uploads: [],
    uploadError: "",
    runError: "",
    runSummary: null
  };
}

function resetAgents(status: AgentStatus) {
  return initialAgents.map((agent) => ({
    ...agent,
    status,
    progress: 0,
    currentTask: "Waiting for workflow handoff"
  }));
}

function appendAssistantDelta(
  messages: ThreadMessage[],
  messageId: string,
  delta: string
) {
  const existing = messages.find((message) => message.id === messageId);
  if (!existing) {
    return [
      ...messages,
      {
        id: messageId,
        role: "assistant" as const,
        agentId: "writer" as const,
        createdAt: timeLabel(),
        content: delta
      }
    ];
  }
  return messages.map((message) =>
    message.id === messageId
      ? {
          ...message,
          content: `${message.content}${delta}`
        }
      : message
  );
}

function upsertArtifact(artifacts: Artifact[], artifact: Artifact) {
  const existing = artifacts.find((item) => item.id === artifact.id);
  if (!existing) {
    return [...artifacts, artifact];
  }
  const versions = [
    ...existing.versions,
    ...artifact.versions.filter(
      (version) => !existing.versions.some((item) => item.id === version.id)
    )
  ] as NonEmptyArray<Artifact["versions"][number]>;
  return artifacts.map((item) =>
    item.id === artifact.id
      ? {
          ...artifact,
          versions
        }
      : item
  );
}

function timeLabel() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}
