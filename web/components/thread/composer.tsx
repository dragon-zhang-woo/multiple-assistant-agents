"use client";

import { FormEvent, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ComposerProps {
  onSendMessage: (content: string) => void;
}

export function Composer({ onSendMessage }: ComposerProps) {
  const [value, setValue] = useState("");

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSendMessage(value);
    setValue("");
  }

  return (
    <div className="sticky bottom-0 shrink-0 bg-paper px-5 pb-5 pt-3">
      <form
        onSubmit={onSubmit}
        className="mx-auto max-w-3xl rounded-xl border border-border bg-background/55 p-2"
      >
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Ask the research team to inspect a paper, revise a section, or compare methods..."
          className="min-h-[86px] border-0 bg-transparent px-3 py-2 focus:border-0"
        />
        <div className="flex items-center justify-between px-1 pb-1">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Button type="button" variant="quiet" size="icon" aria-label="Attach file">
              <Paperclip className="h-4 w-4" />
            </Button>
            Mock workflow · streaming-ready
          </div>
          <Button type="submit" size="icon" aria-label="Send message">
            <ArrowUp className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
