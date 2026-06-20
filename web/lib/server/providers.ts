import { getMergedEnv, getServerEnv } from "@/lib/server/env";

export type ProviderId = "auto" | "deepseek" | "dashscope" | "mock";

export interface ProviderInfo {
  id: ProviderId;
  label: string;
  configured: boolean;
  defaultModel: string;
  baseUrl: string;
  note: string;
}

export function getProviderInfo() {
  const deepseek: ProviderInfo = {
    id: "deepseek",
    label: "DeepSeek",
    configured: hasUsableApiKey(getServerEnv("DEEPSEEK_API_KEY")),
    defaultModel: getServerEnv("DEEPSEEK_MODEL") || "deepseek-v4-flash",
    baseUrl: getServerEnv("DEEPSEEK_BASE_URL") || "https://api.deepseek.com",
    note: "OpenAI-compatible DeepSeek provider"
  };
  const dashscope: ProviderInfo = {
    id: "dashscope",
    label: "Qwen / DashScope",
    configured: hasUsableApiKey(getServerEnv("DASHSCOPE_API_KEY")),
    defaultModel: getServerEnv("DASHSCOPE_MODEL") || "qwen-turbo",
    baseUrl:
      getServerEnv("DASHSCOPE_BASE_URL") ||
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    note: "OpenAI-compatible Qwen provider"
  };
  const mock: ProviderInfo = {
    id: "mock",
    label: "Mock",
    configured: true,
    defaultModel: "deterministic-mock",
    baseUrl: "local",
    note: "No API key required"
  };

  return {
    providers: [deepseek, dashscope, mock],
    defaultProvider: deepseek.configured
      ? "deepseek"
      : dashscope.configured
        ? "dashscope"
        : "mock"
  };
}

export function normalizeProvider(value: unknown): ProviderId {
  if (value === "qwen") {
    return "dashscope";
  }
  if (
    value === "auto" ||
    value === "deepseek" ||
    value === "dashscope" ||
    value === "mock"
  ) {
    return value;
  }
  return "auto";
}

export function providerIsConfigured(provider: ProviderId) {
  if (provider === "mock" || provider === "auto") {
    return true;
  }
  return getProviderInfo().providers.some(
    (item) => item.id === provider && item.configured
  );
}

export function providerMissingMessage(provider: ProviderId) {
  if (provider === "deepseek") {
    return "DeepSeek API key is not configured on the server. Set DEEPSEEK_API_KEY in web/.env.local or the shell environment.";
  }
  if (provider === "dashscope") {
    return "Qwen / DashScope API key is not configured on the server. Set DASHSCOPE_API_KEY in web/.env.local or the shell environment.";
  }
  return "Selected provider is not configured.";
}

function hasUsableApiKey(value: string) {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return ![
    "your_key_here",
    "your_deepseek_key_here",
    "your_dashscope_key_here",
    "changeme",
    "replace_me"
  ].includes(normalized);
}

export function buildChildEnv(model: string | undefined, provider: ProviderId) {
  const env: NodeJS.ProcessEnv = {
    ...getMergedEnv(),
    PYTHONIOENCODING: "utf-8"
  };
  if (provider === "deepseek" && model?.trim()) {
    env.DEEPSEEK_MODEL = model.trim();
  }
  if (provider === "dashscope" && model?.trim()) {
    env.DASHSCOPE_MODEL = model.trim();
  }
  return env;
}
