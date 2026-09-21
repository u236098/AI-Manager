"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowUpDown } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface PostWithMetrics {
  id: number;
  platform: string;
  username: string;
  post_type: string | null;
  caption: string | null;
  published_at: string | null;
  thumbnail_url: string | null;
  media_url: string | null;
  reach: number | null;
  views: number | null;
  likes: number | null;
  saves: number | null;
  shares: number | null;
  comments: number | null;
  followers_from_post: number | null;
  avg_watch_time: number | null;
}

type SortKey = "published_at" | "reach" | "views" | "likes" | "saves" | "shares";

function fmt(n: number | null) {
  if (n == null) return "-";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function formatDate(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "2-digit",
  });
}

export default function PostsPage() {
  const [platform, setPlatform] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("published_at");
  const [sortDesc, setSortDesc] = useState(true);

  const { data: posts, isLoading } = useQuery<PostWithMetrics[]>({
    queryKey: ["posts-with-metrics"],
    queryFn: () => fetch(`${API}/dashboard/posts-with-metrics?limit=200`).then((r) => r.json()),
  });

  const filtered = (posts ?? [])
    .filter((p) => platform === "all" || p.platform === platform)
    .sort((a, b) => {
      const av = a[sortKey] ?? (sortKey === "published_at" ? "" : -1);
      const bv = b[sortKey] ?? (sortKey === "published_at" ? "" : -1);
      if (av < bv) return sortDesc ? 1 : -1;
      if (av > bv) return sortDesc ? -1 : 1;
      return 0;
    });

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDesc(!sortDesc);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  function SortHeader({ label, field }: { label: string; field: SortKey }) {
    return (
      <button
        onClick={() => toggleSort(field)}
        className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
      >
        {label}
        <ArrowUpDown size={12} className={sortKey === field ? "text-accent" : ""} />
      </button>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">Posts</h2>
        <div className="flex gap-1 bg-muted rounded-lg p-0.5">
          {["all", "instagram", "tiktok"].map((p) => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={`px-3 py-1 text-xs rounded-md transition-colors capitalize ${
                platform === p
                  ? "bg-card text-foreground font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {p === "all" ? "All" : p === "instagram" ? "Instagram" : "TikTok"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-muted-foreground">Loading posts...</div>
      ) : (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 w-12">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    #
                  </span>
                </th>
                <th className="text-left px-4 py-3">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Post
                  </span>
                </th>
                <th className="text-left px-4 py-3">
                  <SortHeader label="Date" field="published_at" />
                </th>
                <th className="text-right px-4 py-3">
                  <SortHeader label="Reach" field="reach" />
                </th>
                <th className="text-right px-4 py-3">
                  <SortHeader label="Views" field="views" />
                </th>
                <th className="text-right px-4 py-3">
                  <SortHeader label="Likes" field="likes" />
                </th>
                <th className="text-right px-4 py-3">
                  <SortHeader label="Saves" field="saves" />
                </th>
                <th className="text-right px-4 py-3">
                  <SortHeader label="Shares" field="shares" />
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr key={p.id} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
                  <td className="px-4 py-3 text-muted-foreground text-xs">{i + 1}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          p.platform === "instagram"
                            ? "bg-[#e1306c]/10 text-[#e1306c]"
                            : "bg-foreground/10 text-foreground"
                        }`}
                      >
                        {p.platform === "instagram" ? "IG" : "TT"}
                      </span>
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground capitalize"
                      >
                        {p.post_type}
                      </span>
                      <span className="truncate max-w-[250px]">
                        {p.caption?.slice(0, 60) || "(no caption)"}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDate(p.published_at)}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmt(p.reach)}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmt(p.views)}</td>
                  <td className="px-4 py-3 text-right">{fmt(p.likes)}</td>
                  <td className="px-4 py-3 text-right">{fmt(p.saves)}</td>
                  <td className="px-4 py-3 text-right">{fmt(p.shares)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-3 text-xs text-muted-foreground border-t border-border">
            {filtered.length} posts
          </div>
        </div>
      )}
    </div>
  );
}
