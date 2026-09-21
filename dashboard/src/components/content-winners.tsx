import { ArrowUp, ArrowDown, Minus } from "lucide-react";

interface Theme {
  category: string;
  statement: string;
  vs_median: number | null;
  sample_size: number | null;
  confidence: number | null;
}

interface Props {
  themes: Theme[];
}

export function ContentWinners({ themes }: Props) {
  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <h3 className="font-semibold mb-4">Content Winners</h3>
      <div className="space-y-3">
        {themes.map((t) => {
          const ratio = t.vs_median ?? 1;
          const isUp = ratio > 1.1;
          const isDown = ratio < 0.9;
          return (
            <div key={t.category} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="capitalize text-sm font-medium">{t.category}</span>
                {t.sample_size && (
                  <span className="text-xs text-muted-foreground">
                    ({t.sample_size} posts)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className={`text-sm font-semibold ${
                    isUp ? "text-positive" : isDown ? "text-negative" : "text-muted-foreground"
                  }`}
                >
                  {ratio.toFixed(1)}x
                </span>
                {isUp ? (
                  <ArrowUp size={14} className="text-positive" />
                ) : isDown ? (
                  <ArrowDown size={14} className="text-negative" />
                ) : (
                  <Minus size={14} className="text-muted-foreground" />
                )}
              </div>
            </div>
          );
        })}
        {themes.length === 0 && (
          <p className="text-muted-foreground text-sm">
            Run analytics to see content theme performance.
          </p>
        )}
      </div>
    </div>
  );
}
