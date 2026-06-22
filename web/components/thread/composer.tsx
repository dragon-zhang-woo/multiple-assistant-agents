"use client";

import { ChangeEvent, FormEvent, useRef, useState } from "react";
import { ArrowUp, Loader2, Paperclip, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { UploadedPdf } from "@/types/research";

interface ComposerProps {
  onSendMessage: (content: string) => void;
  onUploadFiles: (files: FileList | File[]) => Promise<void>;
  onRemoveUpload: (id: string) => void;
  uploads: UploadedPdf[];
  uploadError: string;
  isRunning: boolean;
}

export function Composer({
  onSendMessage,
  onUploadFiles,
  onRemoveUpload,
  uploads,
  uploadError,
  isRunning
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isRunning) {
      return;
    }
    onSendMessage(value);
    setValue("");
  }

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length) {
      return;
    }
    setUploading(true);
    await onUploadFiles(files);
    setUploading(false);
    event.target.value = "";
  }

  return (
    <div className="sticky bottom-0 shrink-0 bg-paper px-5 pb-4 pt-2">
      <form
        onSubmit={onSubmit}
        className="mx-auto max-w-3xl rounded-xl border border-border/80 bg-background/55 p-2 transition-colors focus-within:border-foreground/35"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={onFileChange}
        />
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="输入科研问题，例如：近年来 Agent Memory 有哪些研究方向？"
          className="min-h-[70px] border-0 bg-transparent px-3 py-2 focus:border-0"
          disabled={isRunning}
        />
        {(uploads.length > 0 || uploadError) && (
          <div className="flex flex-wrap gap-2 px-2 pb-2">
            {uploads.map((file) => (
              <span
                key={file.id}
                className="inline-flex max-w-[220px] items-center gap-1 rounded-md border border-border bg-paper px-2 py-1 text-xs text-muted-foreground"
              >
                <span className="truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => onRemoveUpload(file.id)}
                  className="rounded-sm p-0.5 hover:bg-accent hover:text-foreground"
                  aria-label={`移除 ${file.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            {uploadError && (
              <span className="text-xs text-muted-foreground">{uploadError}</span>
            )}
          </div>
        )}
        <div className="flex items-center justify-between px-1 pb-0.5">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Button
              type="button"
              variant="quiet"
              size="icon"
              aria-label="Attach PDF"
              disabled={isRunning || uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </Button>
            SSE workflow · PDF optional
          </div>
          <Button
            type="submit"
            size="icon"
            aria-label="Send message"
            disabled={isRunning || !value.trim()}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
