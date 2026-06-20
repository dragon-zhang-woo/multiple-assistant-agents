import type { ChatRequest, ChatStreamEvent, ChatTransport } from "@/lib/chat/events";

export class SseChatTransport implements ChatTransport {
  async *sendMessage(request: ChatRequest): AsyncIterable<ChatStreamEvent> {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        topic: request.topic,
        provider: request.settings.provider,
        model: request.settings.model,
        maxPapers: request.settings.maxPapers,
        candidatePool: request.settings.candidatePool,
        minRelevance: request.settings.minRelevance,
        sort: request.settings.sort,
        mockMode: request.settings.mockMode,
        uploads: request.uploads
      })
    });

    if (!response.ok || !response.body) {
      throw new Error(await response.text());
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const rawEvent of events) {
        const data = rawEvent
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.replace(/^data:\s?/, ""))
          .join("\n")
          .trim();
        if (!data) {
          continue;
        }
        yield JSON.parse(data) as ChatStreamEvent;
      }
    }
  }
}
