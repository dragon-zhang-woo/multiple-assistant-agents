"use client";

import { BookOpen, ChevronDown, Clock3, FileText, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { ResearchProject } from "@/types/research";

interface ResearchSidebarProps {
  projects: ResearchProject[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
}

export function ResearchSidebar({
  projects,
  activeProjectId,
  onSelectProject
}: ResearchSidebarProps) {
  return (
    <aside className="hidden h-full w-[260px] shrink-0 border-r border-border bg-background/70 lg:flex lg:flex-col">
      <div className="flex h-14 items-center justify-between px-4">
        <div>
          <div className="text-sm font-semibold">Research Desk</div>
          <div className="text-xs text-muted-foreground">multiple-assistant-agents</div>
        </div>
        <Button variant="quiet" size="icon" aria-label="切换工作区">
          <ChevronDown className="h-4 w-4" />
        </Button>
      </div>
      <div className="px-3 pb-3">
        <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-paper px-3 text-xs text-muted-foreground">
          <Search className="h-3.5 w-3.5" />
          Search threads
        </div>
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
        </div>
      </div>
      <Separator />
      <div className="p-3">
        <button className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs text-muted-foreground hover:bg-accent hover:text-foreground">
          <BookOpen className="h-4 w-4" />
          Local memory and run logs
        </button>
      </div>
    </aside>
  );
}
