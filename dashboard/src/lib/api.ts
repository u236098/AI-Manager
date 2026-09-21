const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export interface Account {
  id: number;
  platform: string;
  username: string;
  display_name: string | null;
  connected_at: string | null;
}

export interface ProfileSnapshot {
  id: number;
  captured_at: string;
  username: string;
  bio: string | null;
  follower_count: number | null;
  following_count: number | null;
  post_count: number | null;
}

export interface Memory {
  id: number;
  knowledge_type: string;
  category: string;
  statement: string;
  evidence_post_ids: number[] | null;
  metrics_considered: Record<string, unknown> | null;
  sample_size: number | null;
  confidence: number | null;
  updated_at: string;
}

export interface Recommendation {
  id: number;
  agent: string;
  category: string;
  summary: string;
  detail: string | null;
  reasoning: string | null;
  evidence_post_ids: number[] | null;
  confidence: number | null;
  priority: number | null;
  status: string;
  created_at: string | null;
}

export interface AnalyticsResult {
  account: string;
  platform: string;
  total_posts: number;
  baseline: Record<string, unknown>;
  outliers: unknown[];
  content_clusters: Record<string, unknown>;
  evolution: Record<string, unknown>;
  observations_stored: number;
  [key: string]: unknown;
}

export const api = {
  accounts: {
    list: () => fetchJSON<Account[]>("/accounts/"),
    sync: (id: number) => fetchJSON<unknown>(`/accounts/${id}/sync`, { method: "POST" }),
    profileHistory: (id: number) => fetchJSON<ProfileSnapshot[]>(`/accounts/${id}/profile-history`),
    enrichInsights: (id: number) => fetchJSON<unknown>(`/accounts/${id}/enrich-insights`, { method: "POST" }),
  },
  manager: {
    brief: () => fetchJSON<Record<string, unknown>>("/manager/brief/today"),
    weekly: () => fetchJSON<Record<string, unknown>>("/manager/brief/weekly"),
    memories: (creatorId?: number) => fetchJSON<Memory[]>(`/manager/memory?creator_id=${creatorId ?? 1}`),
    recommendations: (status?: string) => fetchJSON<Recommendation[]>(`/manager/recommendations?status=${status ?? "pending"}`),
    analyzeTikTok: (accountId: number) => fetchJSON<AnalyticsResult>(`/manager/analyze/full/${accountId}`, { method: "POST" }),
    analyzeInstagram: (accountId: number) => fetchJSON<AnalyticsResult>(`/manager/analyze/instagram/${accountId}`, { method: "POST" }),
    analyzeCrossPlatform: () => fetchJSON<Record<string, unknown>>("/manager/analyze/cross-platform", { method: "POST" }),
  },
  posts: {
    list: (accountId: number, limit = 50) => fetchJSON<unknown[]>(`/posts/?account_id=${accountId}&limit=${limit}`),
  },
};
