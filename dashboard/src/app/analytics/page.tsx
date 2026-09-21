"use client";

import { useQuery } from "@tanstack/react-query";
import { PerformanceChart } from "@/components/performance-chart";
import { ContentWinners } from "@/components/content-winners";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function AnalyticsPage() {
  const { data: timeline } = useQuery({
    queryKey: ["dashboard-timeline"],
    queryFn: () => fetch(`${API}/dashboard/performance-timeline`).then((r) => r.json()),
  });

  const { data: themes } = useQuery({
    queryKey: ["dashboard-themes"],
    queryFn: () => fetch(`${API}/dashboard/content-themes`).then((r) => r.json()),
  });

  const { data: memories } = useQuery({
    queryKey: ["manager-memories"],
    queryFn: () => fetch(`${API}/manager/memory`).then((r) => r.json()),
  });

  const facts = (memories ?? []).filter(
    (m: { knowledge_type: string }) => m.knowledge_type === "FACT"
  );
  const observations = (memories ?? []).filter(
    (m: { knowledge_type: string }) => m.knowledge_type === "OBSERVATION"
  );
  const hypotheses = (memories ?? []).filter(
    (m: { knowledge_type: string }) => m.knowledge_type === "HYPOTHESIS"
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h2 className="text-xl font-bold">Analytics</h2>

      {timeline && timeline.length > 0 && <PerformanceChart data={timeline} />}

      <div className="grid grid-cols-2 gap-4">
        <ContentWinners themes={themes ?? []} />

        <div className="bg-card rounded-xl border border-border p-5">
          <h3 className="font-semibold mb-4">Knowledge Base</h3>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-accent">{facts.length}</p>
              <p className="text-xs text-muted-foreground">Facts</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-positive">{observations.length}</p>
              <p className="text-xs text-muted-foreground">Observations</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-warning">{hypotheses.length}</p>
              <p className="text-xs text-muted-foreground">Hypotheses</p>
            </div>
          </div>
        </div>
      </div>

      {/* Observations List */}
      <div className="bg-card rounded-xl border border-border p-5">
        <h3 className="font-semibold mb-4">All Observations</h3>
        <div className="space-y-3">
          {observations.map(
            (o: {
              id: number;
              category: string;
              statement: string;
              confidence: number | null;
              sample_size: number | null;
            }) => (
              <div key={o.id} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
                <div className="flex-1">
                  <p className="text-sm">{o.statement}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-muted-foreground">{o.category}</span>
                    {o.confidence != null && (
                      <span className="text-xs text-muted-foreground">
                        {(o.confidence * 100).toFixed(0)}% confidence
                      </span>
                    )}
                    {o.sample_size != null && (
                      <span className="text-xs text-muted-foreground">
                        n={o.sample_size}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* Hypotheses */}
      {hypotheses.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-5">
          <h3 className="font-semibold mb-4">Active Hypotheses</h3>
          <div className="space-y-3">
            {hypotheses.map(
              (h: { id: number; category: string; statement: string; confidence: number | null }) => (
                <div key={h.id} className="py-2 border-b border-border/50 last:border-0">
                  <p className="text-sm">{h.statement}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-muted-foreground">{h.category}</span>
                    {h.confidence != null && (
                      <span className="text-xs text-warning">
                        {(h.confidence * 100).toFixed(0)}% confidence
                      </span>
                    )}
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
