"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, ExternalLink } from "lucide-react";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Account {
  id: number;
  platform: string;
  username: string;
  display_name: string | null;
  connected_at: string | null;
}

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [syncingId, setSyncingId] = useState<number | null>(null);

  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => fetch(`${API}/accounts/`).then((r) => r.json()),
  });

  const syncMutation = useMutation({
    mutationFn: async (id: number) => {
      setSyncingId(id);
      const res = await fetch(`${API}/accounts/${id}/sync`, { method: "POST" });
      return res.json();
    },
    onSettled: () => {
      setSyncingId(null);
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold">Connected Accounts</h2>

      {isLoading ? (
        <div className="text-muted-foreground">Loading accounts...</div>
      ) : (
        <div className="space-y-3">
          {(accounts ?? []).map((acc) => (
            <div
              key={acc.id}
              className="bg-card rounded-xl border border-border p-5 flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg ${
                    acc.platform === "instagram"
                      ? "bg-gradient-to-br from-[#f09433] via-[#e1306c] to-[#bc2a8d]"
                      : "bg-black"
                  }`}
                >
                  {acc.platform === "instagram" ? "IG" : "TT"}
                </div>
                <div>
                  <p className="font-semibold">@{acc.username}</p>
                  <p className="text-sm text-muted-foreground capitalize">{acc.platform}</p>
                  {acc.connected_at && (
                    <p className="text-xs text-muted-foreground">
                      Connected {new Date(acc.connected_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => syncMutation.mutate(acc.id)}
                  disabled={syncingId === acc.id}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-muted transition-colors disabled:opacity-50"
                >
                  <RefreshCw
                    size={14}
                    className={syncingId === acc.id ? "animate-spin" : ""}
                  />
                  {syncingId === acc.id ? "Syncing..." : "Sync"}
                </button>
                {acc.platform === "instagram" && (
                  <a
                    href={`https://instagram.com/${acc.username}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
                  >
                    <ExternalLink size={14} />
                  </a>
                )}
                {acc.platform === "tiktok" && (
                  <a
                    href={`https://tiktok.com/@${acc.username}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
                  >
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {syncMutation.data && (
        <div className="bg-muted rounded-xl p-4">
          <h3 className="font-medium text-sm mb-2">Last Sync Result</h3>
          <pre className="text-xs text-muted-foreground overflow-auto">
            {JSON.stringify(syncMutation.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
