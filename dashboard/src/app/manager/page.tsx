"use client";

import { useState, useEffect } from "react";
import { Brain, TrendingUp, Lightbulb, AlertTriangle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Memory {
  id: number;
  knowledge_type: string;
  category: string;
  statement: string;
  confidence: number | null;
  sample_size: number | null;
  updated_at: string;
}

interface Recommendation {
  id: number;
  agent: string;
  category: string;
  summary: string;
  detail: string | null;
  reasoning: string | null;
  confidence: number | null;
  priority: number | null;
  status: string;
}

const TYPE_ICONS: Record<string, typeof Brain> = {
  fact: TrendingUp,
  observation: Lightbulb,
  hypothesis: AlertTriangle,
};

const TYPE_COLORS: Record<string, string> = {
  fact: "text-green-400 bg-green-400/10",
  observation: "text-blue-400 bg-blue-400/10",
  hypothesis: "text-yellow-400 bg-yellow-400/10",
};

export default function ManagerIntelligencePage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [recommendations, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      try {
        const [memRes, recRes] = await Promise.all([
          fetch(`${API}/manager/memory`),
          fetch(`${API}/manager/recommendations?status=pending`),
        ]);
        setMemories(await memRes.json());
        setRecs(await recRes.json());
      } catch {
        // API unavailable
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered =
    filter === "all"
      ? memories
      : memories.filter((m) => m.knowledge_type === filter);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
          <Brain size={20} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold">Manager Intelligence</h2>
          <p className="text-sm text-muted-foreground">
            Knowledge base and pending recommendations — connect via MCP for AI
            interaction
          </p>
        </div>
      </div>

      {/* Pending Recommendations */}
      {recommendations.length > 0 && (
        <section className="mb-8">
          <h3 className="text-lg font-semibold mb-3">
            Pending Recommendations
          </h3>
          <div className="space-y-3">
            {recommendations.map((r) => (
              <div
                key={r.id}
                className="bg-card rounded-xl border border-border p-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{r.summary}</p>
                    {r.reasoning && (
                      <p className="text-sm text-muted-foreground mt-1">
                        {r.reasoning}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    {r.confidence != null && (
                      <span className="text-xs text-muted-foreground">
                        {(r.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                    <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent">
                      {r.category}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Knowledge Base */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Knowledge Base</h3>
          <div className="flex gap-1">
            {["all", "fact", "observation", "hypothesis"].map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-3 py-1 rounded-lg text-xs capitalize transition-colors ${
                  filter === t
                    ? "bg-accent text-white"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-muted-foreground">
            Loading...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No {filter === "all" ? "" : filter} memories yet. Run analysis to
            generate insights.
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((m) => {
              const Icon = TYPE_ICONS[m.knowledge_type] || Brain;
              const color =
                TYPE_COLORS[m.knowledge_type] || "text-gray-400 bg-gray-400/10";
              return (
                <div
                  key={m.id}
                  className="bg-card rounded-xl border border-border p-4 flex items-start gap-3"
                >
                  <div className={`p-1.5 rounded-lg ${color}`}>
                    <Icon size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{m.statement}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                      <span className="capitalize">{m.category}</span>
                      {m.confidence != null && (
                        <span>
                          Confidence: {(m.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                      {m.sample_size != null && (
                        <span>n={m.sample_size}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
