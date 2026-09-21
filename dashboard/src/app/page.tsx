"use client";

import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/stat-card";
import { PerformanceChart } from "@/components/performance-chart";
import { ContentWinners } from "@/components/content-winners";
import { ManagerBrief } from "@/components/manager-brief";
import { TopPosts } from "@/components/top-posts";
import { MessageSquare } from "lucide-react";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function formatFollowers(n: number) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Overview() {
  const [chatInput, setChatInput] = useState("");

  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: () => fetch(`${API}/dashboard/overview`).then((r) => r.json()),
  });

  const { data: timeline } = useQuery({
    queryKey: ["dashboard-timeline"],
    queryFn: () => fetch(`${API}/dashboard/performance-timeline`).then((r) => r.json()),
  });

  const { data: themes } = useQuery({
    queryKey: ["dashboard-themes"],
    queryFn: () => fetch(`${API}/dashboard/content-themes`).then((r) => r.json()),
  });

  if (loadingOverview) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-muted-foreground">Loading dashboard...</div>
      </div>
    );
  }

  const ig = overview?.accounts?.find(
    (a: { platform: string; followers: number | null }) => a.platform === "instagram" && a.followers
  );
  const tt = overview?.accounts?.find(
    (a: { platform: string; followers: number | null }) => a.platform === "tiktok" && a.followers
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <p className="text-muted-foreground text-sm mb-1">
          {new Date().toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </p>
        <h2 className="text-2xl font-bold">
          {getGreeting()}, Kobby.
        </h2>
      </div>

      {/* Chat Bar */}
      <div className="bg-card rounded-xl border border-border p-1">
        <div className="flex items-center gap-3 px-4 py-2">
          <MessageSquare size={18} className="text-muted-foreground" />
          <input
            type="text"
            placeholder="Ask Kobby Manager..."
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && chatInput.trim()) {
                window.location.href = `/manager?q=${encodeURIComponent(chatInput)}`;
              }
            }}
          />
          <span className="text-xs text-muted-foreground">Press Enter</span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Instagram"
          value={ig ? formatFollowers(ig.followers) : "-"}
          sublabel={ig ? `${ig.post_count} posts` : "Not connected"}
          color="text-[#e1306c]"
        />
        <StatCard
          label="TikTok"
          value={tt ? formatFollowers(tt.followers) : "-"}
          sublabel={tt ? `${tt.post_count} posts` : "Not connected"}
          color="text-foreground"
        />
        <StatCard
          label="Total Audience"
          value={formatFollowers(overview?.total_followers ?? 0)}
          sublabel="across all platforms"
          color="text-accent"
        />
      </div>

      {/* Manager Brief */}
      <ManagerBrief
        observations={overview?.observations ?? []}
        hypotheses={overview?.hypotheses ?? []}
      />

      {/* Performance Chart */}
      {timeline && timeline.length > 0 && <PerformanceChart data={timeline} />}

      {/* Bottom Row: Content Winners + Top Posts */}
      <div className="grid grid-cols-2 gap-4">
        <ContentWinners themes={themes ?? []} />
        <TopPosts posts={overview?.top_posts ?? []} />
      </div>
    </div>
  );
}
