"use client";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Sparkles, FileText } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  evidence?: number[];
  confidence?: number;
}

export default function ManagerPage() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") || "";
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(initialQ);
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (initialQ && messages.length === 0) {
      sendMessage(initialQ);
      setInput("");
    }
  }, []);

  async function sendMessage(text: string) {
    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/manager/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.response || data.raw || JSON.stringify(data),
        evidence: data.evidence_post_ids,
        confidence: data.confidence,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Something went wrong"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-3rem)]">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
          <Sparkles size={20} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold">Kobby Manager</h2>
          <p className="text-sm text-muted-foreground">
            AI-powered talent management with evidence-backed recommendations
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center py-20">
            <Sparkles size={40} className="mx-auto text-accent/30 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              What should I post next?
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Ask about strategy, content ideas, performance, or anything else.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              {[
                "What should I post tomorrow?",
                "Which content themes are working?",
                "How is my reach trending?",
                "Suggest a content experiment",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    setInput(q);
                    sendMessage(q);
                    setInput("");
                  }}
                  className="px-3 py-1.5 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:border-accent transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-accent text-white"
                  : "bg-muted"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.evidence && msg.evidence.length > 0 && (
                <div className="flex items-center gap-1 mt-2 pt-2 border-t border-black/10">
                  <FileText size={12} className="text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    Evidence: {msg.evidence.map((id) => `#${id}`).join(", ")}
                  </span>
                </div>
              )}
              {msg.confidence != null && (
                <p className="text-xs text-muted-foreground mt-1">
                  Confidence: {(msg.confidence * 100).toFixed(0)}%
                </p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="bg-card rounded-xl border border-border p-1 mt-2">
        <div className="flex items-center gap-3 px-4 py-2">
          <input
            type="text"
            placeholder="Ask Kobby Manager..."
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && input.trim() && !loading) {
                sendMessage(input.trim());
                setInput("");
              }
            }}
            disabled={loading}
          />
          <button
            onClick={() => {
              if (input.trim() && !loading) {
                sendMessage(input.trim());
                setInput("");
              }
            }}
            disabled={loading || !input.trim()}
            className="p-2 rounded-lg bg-accent text-white disabled:opacity-40 hover:bg-accent-light transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
