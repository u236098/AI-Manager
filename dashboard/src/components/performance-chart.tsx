"use client";

import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface TimelinePoint {
  month: string;
  platform: string;
  posts: number;
  avg_reach: number | null;
  avg_views: number | null;
  avg_likes: number | null;
  total_reach: number | null;
  total_views: number | null;
}

interface Props {
  data: TimelinePoint[];
}

type Metric = "avg_likes" | "avg_reach" | "avg_views";

const METRIC_LABELS: Record<Metric, string> = {
  avg_likes: "Avg Likes",
  avg_reach: "Avg Reach",
  avg_views: "Avg Views",
};

function formatMonth(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

function formatNumber(n: number) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toFixed(0);
}

export function PerformanceChart({ data }: Props) {
  const [metric, setMetric] = useState<Metric>("avg_likes");

  const igData = data
    .filter((d) => d.platform === "instagram")
    .map((d) => ({ month: formatMonth(d.month), value: d[metric] ?? 0, posts: d.posts }));

  const ttData = data
    .filter((d) => d.platform === "tiktok")
    .map((d) => ({ month: formatMonth(d.month), value: d[metric] ?? 0, posts: d.posts }));

  const months = [...new Set([...igData.map((d) => d.month), ...ttData.map((d) => d.month)])];
  const merged = months.map((m) => ({
    month: m,
    instagram: igData.find((d) => d.month === m)?.value ?? null,
    tiktok: ttData.find((d) => d.month === m)?.value ?? null,
  }));

  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold">Performance</h3>
        <div className="flex gap-1 bg-muted rounded-lg p-0.5">
          {(Object.keys(METRIC_LABELS) as Metric[]).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                metric === m
                  ? "bg-card text-foreground font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {METRIC_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={merged} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <defs>
            <linearGradient id="igGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#e1306c" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#e1306c" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="ttGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickFormatter={formatNumber}
            tickLine={false}
            axisLine={false}
            width={45}
          />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "none",
              borderRadius: "8px",
              color: "#fff",
              fontSize: "12px",
            }}
            formatter={(value: unknown) => [formatNumber(Number(value ?? 0)), ""]}
          />
          <Area
            type="monotone"
            dataKey="instagram"
            stroke="#e1306c"
            strokeWidth={2}
            fill="url(#igGrad)"
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="tiktok"
            stroke="#6366f1"
            strokeWidth={2}
            fill="url(#ttGrad)"
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>

      <div className="flex items-center gap-4 mt-3 justify-center">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-[#e1306c] rounded" />
          <span className="text-xs text-muted-foreground">Instagram</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-accent rounded" />
          <span className="text-xs text-muted-foreground">TikTok</span>
        </div>
      </div>
    </div>
  );
}
