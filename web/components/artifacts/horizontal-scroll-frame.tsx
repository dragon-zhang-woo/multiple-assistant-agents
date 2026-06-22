"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface HorizontalScrollFrameProps {
  children: ReactNode;
  className?: string;
}

export function HorizontalScrollFrame({
  children,
  className
}: HorizontalScrollFrameProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollState, setScrollState] = useState({
    max: 0,
    value: 0,
    scrollable: false
  });

  function measure() {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    const max = Math.max(0, element.scrollWidth - element.clientWidth);
    setScrollState({
      max,
      value: Math.min(element.scrollLeft, max),
      scrollable: max > 1
    });
  }

  useEffect(() => {
    measure();
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    const resizeObserver = new ResizeObserver(measure);
    resizeObserver.observe(element);
    if (element.firstElementChild) {
      resizeObserver.observe(element.firstElementChild);
    }
    window.addEventListener("resize", measure);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  function scrollTo(next: number) {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    const value = Math.max(0, Math.min(scrollState.max, next));
    element.scrollLeft = value;
    setScrollState((current) => ({
      ...current,
      value
    }));
  }

  return (
    <div className={cn("relative max-w-full", className)}>
      <div
        ref={scrollRef}
        className="artifact-horizontal-scroll"
        onScroll={measure}
      >
        {children}
      </div>
      {scrollState.scrollable && (
        <div className="sticky bottom-0 z-10 flex items-center gap-2 border-t border-border/80 bg-paper/95 px-3 py-2 backdrop-blur-none">
          <button
            type="button"
            className="rounded-md border border-border/80 bg-background px-1.5 py-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Scroll artifact left"
            onClick={() => scrollTo(scrollState.value - 220)}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <input
            type="range"
            min={0}
            max={scrollState.max}
            value={scrollState.value}
            aria-label="Artifact horizontal scroll"
            className="artifact-scroll-range"
            onChange={(event) => scrollTo(Number(event.target.value))}
            onInput={(event) => scrollTo(Number(event.currentTarget.value))}
          />
          <button
            type="button"
            className="rounded-md border border-border/80 bg-background px-1.5 py-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Scroll artifact right"
            onClick={() => scrollTo(scrollState.value + 220)}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
