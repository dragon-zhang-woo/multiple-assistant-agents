import type { ResearchSession } from "@/types/research";

export const mockResearchSession: ResearchSession = {
  projects: [
    {
      id: "agent-memory",
      name: "Agent Memory Survey",
      updatedAt: "刚刚更新",
      description: "围绕长期记忆、检索增强、隐私风险的多 Agent 调研。",
      status: "active"
    },
    {
      id: "paper-reading",
      name: "Reading Queue",
      updatedAt: "昨天",
      description: "待阅读论文、摘要抽取和方法矩阵。",
      status: "draft"
    },
    {
      id: "lab-report",
      name: "实验七报告",
      updatedAt: "2 天前",
      description: "课程作业结构、运行日志与评分点对齐。",
      status: "draft"
    }
  ],
  agents: [
    {
      id: "planner",
      name: "Planner",
      role: "拆解任务并安排调研路线",
      status: "done",
      progress: 100,
      currentTask: "已完成研究问题拆解"
    },
    {
      id: "scholar",
      name: "Scholar",
      role: "检索 arXiv 与筛选候选论文",
      status: "done",
      progress: 100,
      currentTask: "5 篇论文进入正文，2 篇被过滤"
    },
    {
      id: "reader",
      name: "Reader",
      role: "阅读摘要并抽取方法证据",
      status: "done",
      progress: 100,
      currentTask: "已完成贡献、方法和方向分类"
    },
    {
      id: "critic",
      name: "Critic",
      role: "反思证据不足与风险",
      status: "reviewing",
      progress: 78,
      currentTask: "正在压缩开放问题"
    },
    {
      id: "writer",
      name: "Writer",
      role: "汇总报告和 artifact",
      status: "working",
      progress: 62,
      currentTask: "整理右侧调研报告"
    }
  ],
  messages: [
    {
      id: "m1",
      role: "user",
      createdAt: "12:07",
      content: "近年来 Agent Memory 有哪些研究方向？请检索论文并生成调研报告。"
    },
    {
      id: "m2",
      role: "assistant",
      agentId: "planner",
      createdAt: "12:08",
      artifactIds: ["survey", "matrix"],
      citations: ["Infini Memory", "MemLineage", "GroupMemBench"],
      content:
        "我会把问题拆成四个阶段：先用精确检索式找到与 LLM Agent Memory 直接相关的论文，再过滤低相关候选；随后抽取每篇论文的贡献、方法和证据；最后由 Critic 检查局限，由 Writer 汇总为报告和文献矩阵。\n\n目前检索质量已经比按最新提交排序稳定：正文候选集中在长期记忆架构、检索增强记忆、安全隐私与评测三个方向。"
    },
    {
      id: "m3",
      role: "assistant",
      agentId: "critic",
      createdAt: "12:10",
      artifactIds: ["survey"],
      content:
        "需要注意两类风险。第一，当前阅读主要基于摘要，方法细节和实验设置需要在最终报告前通过全文 PDF 补证。第二，Agent Memory 论文常把检索、数据库、长期上下文管理混在一起，分类时要区分“存储结构”“读写策略”和“应用任务”。"
    }
  ],
  trace: [
    {
      id: "t1",
      agentId: "planner",
      title: "规划检索路线",
      detail: "限定当前系统已实现能力：arXiv、PDF 抽取、统计、JSON 记忆和 Markdown artifact。",
      status: "done",
      timestamp: "12:07:16"
    },
    {
      id: "t2",
      agentId: "scholar",
      title: "展开 arXiv 查询",
      detail: "使用 all:\"agent memory\"、ti/abs:\"agent memory\"、LLM agent AND memory 等组合检索。",
      status: "done",
      timestamp: "12:07:26"
    },
    {
      id: "t3",
      agentId: "reader",
      title: "生成文献矩阵",
      detail: "提取方向、方法、证据和可信度，保留 rejected papers 供审查。",
      status: "done",
      timestamp: "12:07:48"
    },
    {
      id: "t4",
      agentId: "critic",
      title: "反思证据边界",
      detail: "标记摘要证据不足、隐私风险和长期记忆更新策略不一致。",
      status: "reviewing",
      timestamp: "12:08:04"
    },
    {
      id: "t5",
      agentId: "writer",
      title: "更新 artifact",
      detail: "正在生成调研报告、文献矩阵和后续 API 接入代码片段。",
      status: "working",
      timestamp: "12:08:16"
    }
  ],
  artifacts: [
    {
      id: "survey",
      title: "Agent Memory 调研报告",
      kind: "markdown",
      versions: [
        {
          id: "v1",
          label: "v1 摘要版",
          createdAt: "12:08",
          summary: "按研究方向组织的初稿。",
          content:
            "## 执行摘要\n\nAgent Memory 研究正在从简单会话缓存转向长期、可维护、可审计的记忆系统。当前代表方向包括长期记忆架构、检索增强记忆、安全隐私与评测。\n\n## 方向一：长期记忆架构\n\nMemLineage 和 Infini Memory 关注持久记忆如何跨会话维护事实，并保留证据来源。\n\n## 方向二：检索增强记忆\n\n相关工作把 Agent Memory 视为数据库或主题文档集合，重点解决写入、检索、冲突消解和维护成本。\n\n## 方向三：安全隐私与评测\n\nPrivacy Risks 和 GroupMemBench 说明记忆系统不仅要“记得住”，也要能被评测、约束和删除。\n\n## 下一步\n\n需要补充全文阅读，确认实验任务、基线和指标，避免只基于摘要下结论。"
        },
        {
          id: "v2",
          label: "v2 评分对齐",
          createdAt: "12:12",
          summary: "补充课程作业评分点。",
          content:
            "## 评分对齐\n\n- 多 Agent：Planner、Scholar、Reader、Critic、Writer。\n- 推理方法：Planner 使用规划，Scholar 使用 ReAct 风格检索，Critic 使用 Reflection。\n- 记忆：短期 messages/trace，长期 JSON memory。\n- 工具：arXiv、PDF extractor、统计工具。\n\n## 质量改进\n\n本版默认按相关性排序，并把低相关候选写入 rejected_papers，避免物理实验、视频理解等偏题论文进入正文。"
        }
      ]
    },
    {
      id: "matrix",
      title: "Literature Matrix",
      kind: "literature-matrix",
      versions: [
        {
          id: "v1",
          label: "v1",
          createdAt: "12:09",
          summary: "5 篇高相关论文。",
          content: "Structured literature matrix",
          literature: [
            {
              id: "p1",
              title: "Infini Memory",
              year: "2026",
              direction: "检索增强记忆",
              method: "Topic documents for long-term LLM agent memory",
              evidence: "强调 persistent memory、changing facts、relevant evidence。",
              confidence: "high"
            },
            {
              id: "p2",
              title: "MemLineage",
              year: "2026",
              direction: "长期记忆架构",
              method: "Lineage-guided memory enforcement",
              evidence: "为 memory entry 附加 provenance 与 derivation lineage。",
              confidence: "high"
            },
            {
              id: "p3",
              title: "Unveiling Privacy Risks in LLM Agent Memory",
              year: "2025",
              direction: "安全隐私与评测",
              method: "Privacy risk analysis",
              evidence: "聚焦真实应用中记忆带来的隐私攻击面。",
              confidence: "medium"
            },
            {
              id: "p4",
              title: "Is Agent Memory a Database?",
              year: "2026",
              direction: "检索增强记忆",
              method: "Database foundations for agent memory",
              evidence: "重新审视长期 AI Agent Memory 的数据基础。",
              confidence: "high"
            }
          ]
        }
      ]
    },
    {
      id: "code",
      title: "Streaming 接入草图",
      kind: "code",
      versions: [
        {
          id: "v1",
          label: "client hook",
          createdAt: "12:13",
          summary: "后续接 /api/chat 的事件流类型。",
          language: "ts",
          content:
            "export type ChatStreamEvent =\n  | { type: 'message.delta'; messageId: string; delta: string }\n  | { type: 'agent.status'; agentId: AgentId; status: AgentStatus; progress: number }\n  | { type: 'artifact.upsert'; artifact: Artifact }\n  | { type: 'trace.append'; agentId: AgentId; title: string; detail: string };\n\n// Later: replace mock transport with Vercel AI SDK data stream or SSE from /api/chat."
        }
      ]
    }
  ]
};
