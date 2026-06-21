"use client";

import {
  BookOpen,
  Clock3,
  FileText,
  Moon,
  Plus,
  Search,
  SlidersHorizontal,
  Sun
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type {
  ProviderId,
  ProviderInfo,
  ResearchProject,
  ResearchSettings,
  RunSummary
} from "@/types/research";

interface ResearchSidebarProps {
  projects: ResearchProject[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  providers: ProviderInfo[];
  settings: ResearchSettings;
  onSettingsChange: (settings: Partial<ResearchSettings>) => void;
  onSelectProvider: (provider: ProviderId) => void;
  runSummary: RunSummary | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onCreateThread: () => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
}

export function ResearchSidebar({
  projects,
  activeProjectId,
  onSelectProject,
  providers,
  settings,
  onSettingsChange,
  onSelectProvider,
  runSummary,
  theme,
  onToggleTheme,
  onCreateThread,
  searchQuery,
  onSearchQueryChange
}: ResearchSidebarProps) {
  const selectedProvider = providers.find((provider) => provider.id === settings.provider);

  return (
    <aside className="hidden h-full w-[260px] shrink-0 border-r border-border bg-background/70 lg:flex lg:flex-col">
      <div className="flex h-14 items-center justify-between px-4">
        <div>
          <div className="text-sm font-semibold">Research Desk</div>
          <div className="text-xs text-muted-foreground">multiple-assistant-agents</div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="quiet"
            size="icon"
            aria-label="切换暗亮主题"
            onClick={onToggleTheme}
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="quiet"
            size="icon"
            aria-label="新建线程"
            onClick={onCreateThread}
            title="新建线程"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="px-3 pb-3">
        <label className="flex h-9 items-center gap-2 rounded-md border border-border bg-paper px-3 text-xs text-muted-foreground focus-within:border-foreground/35">
          <Search className="h-3.5 w-3.5" />
          <input
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="Search threads"
            className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            aria-label="Search threads"
          />
        </label>
      </div>
      <Separator />
      <div className="flex-1 overflow-y-auto px-2 py-3 quiet-scrollbar">
        <div className="mb-2 px-2 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
          Projects
        </div>
        <div className="space-y-1">
          {projects.map((project) => (
            <button
              key={project.id}
              className={cn(
                "group w-full rounded-md px-2.5 py-2 text-left transition-colors hover:bg-accent",
                project.id === activeProjectId && "bg-accent text-foreground"
              )}
              onClick={() => onSelectProject(project.id)}
            >
              <div className="flex items-start gap-2">
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{project.name}</div>
                  <div className="mt-0.5 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {project.description}
                  </div>
                  <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
                    <Clock3 className="h-3 w-3" />
                    {project.updatedAt}
                  </div>
                </div>
              </div>
            </button>
          ))}
          {projects.length === 0 && (
            <div className="rounded-md border border-border bg-paper/45 px-3 py-4 text-xs leading-5 text-muted-foreground">
              No matching threads.
            </div>
          )}
        </div>
        <Separator className="my-4" />
        <SettingsPanel
          providers={providers}
          settings={settings}
          selectedProvider={selectedProvider}
          onSettingsChange={onSettingsChange}
          onSelectProvider={onSelectProvider}
        />
      </div>
      <Separator />
      <div className="p-3">
        <button className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs text-muted-foreground hover:bg-accent hover:text-foreground">
          <BookOpen className="h-4 w-4" />
          {runSummary
            ? `${runSummary.paperCount} papers + ${runSummary.supportingCount ?? 0} support · ${runSummary.llmMode}`
            : "Local memory and run logs"}
        </button>
      </div>
    </aside>
  );
}

interface SettingsPanelProps {
  providers: ProviderInfo[];
  settings: ResearchSettings;
  selectedProvider?: ProviderInfo;
  onSettingsChange: (settings: Partial<ResearchSettings>) => void;
  onSelectProvider: (provider: ProviderId) => void;
}

function SettingsPanel({
  providers,
  settings,
  selectedProvider,
  onSettingsChange,
  onSelectProvider
}: SettingsPanelProps) {
  return (
    <section className="px-2">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Run Settings
      </div>
      <div className="space-y-3 rounded-md border border-border bg-paper/55 p-3">
        <label className="block">
          <span className="mb-1 block text-[11px] text-muted-foreground">Provider</span>
          <select
            value={settings.provider}
            onChange={(event) => onSelectProvider(event.target.value as ProviderId)}
            className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus:border-foreground/40"
          >
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
          <span>Server key</span>
          <span
            data-testid="provider-key-status"
            className={cn(
              "rounded-full border px-2 py-0.5",
              selectedProvider?.configured
                ? "border-border bg-background"
                : "border-border bg-muted text-muted-foreground"
            )}
          >
            {selectedProvider?.configured ? "configured" : "missing"}
          </span>
        </div>
        <label className="block">
          <span className="mb-1 block text-[11px] text-muted-foreground">Model</span>
          <input
            value={settings.model}
            onChange={(event) => onSettingsChange({ model: event.target.value })}
            className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus:border-foreground/40"
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <NumberField
            label="Papers"
            value={settings.maxPapers}
            min={1}
            max={12}
            onChange={(maxPapers) => onSettingsChange({ maxPapers })}
          />
          <NumberField
            label="Pool"
            value={settings.candidatePool}
            min={0}
            max={80}
            onChange={(candidatePool) => onSettingsChange({ candidatePool })}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <NumberField
            label="Min score"
            value={settings.minRelevance}
            min={0}
            max={12}
            step={0.5}
            onChange={(minRelevance) => onSettingsChange({ minRelevance })}
          />
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">Sort</span>
            <select
              value={settings.sort}
              onChange={(event) =>
                onSettingsChange({
                  sort: event.target.value as ResearchSettings["sort"]
                })
              }
              className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus:border-foreground/40"
            >
              <option value="relevance">relevance</option>
              <option value="submittedDate">submitted</option>
            </select>
          </label>
        </div>
      </div>
    </section>
  );
}

interface NumberFieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}

function NumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange
}: NumberFieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] text-muted-foreground">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus:border-foreground/40"
      />
    </label>
  );
}
