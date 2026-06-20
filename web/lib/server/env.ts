import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(process.cwd(), "..");
const webRoot = process.cwd();

export function getRepoRoot() {
  return repoRoot;
}

export function getWebRoot() {
  return webRoot;
}

export function getMergedEnv() {
  return {
    ...readEnvFiles(),
    ...process.env
  };
}

export function getServerEnv(name: string) {
  const merged = getMergedEnv();
  return merged[name]?.trim() ?? "";
}

function readEnvFiles() {
  const candidates = [
    path.join(repoRoot, ".env"),
    path.join(webRoot, ".env"),
    path.join(webRoot, ".env.local")
  ];
  return candidates.reduce<Record<string, string>>((acc, filePath) => {
    if (!fs.existsSync(filePath)) {
      return acc;
    }
    const parsed = parseEnvFile(fs.readFileSync(filePath, "utf8"));
    return {
      ...acc,
      ...parsed
    };
  }, {});
}

function parseEnvFile(content: string) {
  const values: Record<string, string> = {};
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }
    const index = line.indexOf("=");
    if (index === -1) {
      continue;
    }
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}
