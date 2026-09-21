"use client";

import { useQuery } from "@tanstack/react-query";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function SettingsPage() {
  const { data: config } = useQuery({
    queryKey: ["manager-config"],
    queryFn: () => fetch(`${API}/manager/config`).then((r) => r.json()),
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-bold">Settings</h2>

      <div className="bg-card rounded-xl border border-border p-5">
        <h3 className="font-semibold mb-4">Manager Autonomy</h3>
        <p className="text-sm text-muted-foreground mb-3">
          Current level: <span className="font-medium text-foreground">{config?.autonomy_level ?? "adviser"}</span>
        </p>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between py-1">
            <span>Auto-approve analytics</span>
            <span className={config?.auto_approve_analytics ? "text-positive" : "text-muted-foreground"}>
              {config?.auto_approve_analytics ? "On" : "Off"}
            </span>
          </div>
          <div className="flex items-center justify-between py-1">
            <span>Auto-approve reads</span>
            <span className={config?.auto_approve_reads ? "text-positive" : "text-muted-foreground"}>
              {config?.auto_approve_reads ? "On" : "Off"}
            </span>
          </div>
          <div className="flex items-center justify-between py-1">
            <span>Auto-approve drafts</span>
            <span className={config?.auto_approve_drafts ? "text-positive" : "text-muted-foreground"}>
              {config?.auto_approve_drafts ? "On" : "Off"}
            </span>
          </div>
        </div>
      </div>

      <div className="bg-card rounded-xl border border-border p-5">
        <h3 className="font-semibold mb-4">AI Provider</h3>
        <p className="text-sm text-muted-foreground">
          OpenAI (GPT-5.6 Sol / Terra / Luna)
        </p>
      </div>
    </div>
  );
}
