import { ArrowUp, ArrowDown, Sparkles } from "lucide-react";

interface Observation {
  id: number;
  category: string;
  statement: string;
  confidence: number | null;
  sample_size: number | null;
}

interface Hypothesis {
  id: number;
  category: string;
  statement: string;
  confidence: number | null;
}

interface Props {
  observations: Observation[];
  hypotheses: Hypothesis[];
}

function classify(statement: string): "up" | "down" | "neutral" {
  const lower = statement.toLowerCase();
  if (lower.includes("outperform") || lower.includes("above") || lower.includes("higher") || lower.includes("strong"))
    return "up";
  if (lower.includes("underperform") || lower.includes("below") || lower.includes("lower") || lower.includes("fell") || lower.includes("declining"))
    return "down";
  return "neutral";
}

export function ManagerBrief({ observations, hypotheses }: Props) {
  const topObs = observations.slice(0, 4);
  const topHyp = hypotheses.slice(0, 1);

  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <h3 className="font-semibold mb-4">Manager Brief</h3>

      <div className="space-y-3">
        {topObs.map((o) => {
          const dir = classify(o.statement);
          return (
            <div key={o.id} className="flex items-start gap-2">
              {dir === "up" ? (
                <ArrowUp size={16} className="text-positive mt-0.5 shrink-0" />
              ) : dir === "down" ? (
                <ArrowDown size={16} className="text-negative mt-0.5 shrink-0" />
              ) : (
                <span className="w-4 mt-0.5 shrink-0" />
              )}
              <p className="text-sm leading-relaxed">{o.statement}</p>
            </div>
          );
        })}
      </div>

      {topHyp.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          {topHyp.map((h) => (
            <div key={h.id} className="flex items-start gap-2">
              <Sparkles size={16} className="text-accent mt-0.5 shrink-0" />
              <div>
                <p className="text-sm leading-relaxed">{h.statement}</p>
                {h.confidence != null && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Confidence: {(h.confidence * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {observations.length === 0 && hypotheses.length === 0 && (
        <p className="text-muted-foreground text-sm">
          No insights yet. Connect accounts and run analytics to get started.
        </p>
      )}
    </div>
  );
}
