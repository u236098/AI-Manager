interface TopPost {
  id: number;
  platform: string;
  post_type: string | null;
  caption: string;
  published_at: string | null;
  reach: number | null;
  views: number | null;
  likes: number | null;
  saves: number | null;
  shares: number | null;
  followers_from_post: number | null;
  comments: number | null;
}

interface Props {
  posts: TopPost[];
}

function formatNumber(n: number | null | undefined) {
  if (n == null) return "-";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function platformBadge(platform: string) {
  if (platform === "instagram")
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#e1306c]/10 text-[#e1306c]">
        IG
      </span>
    );
  return (
    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-foreground/10 text-foreground">
      TT
    </span>
  );
}

export function TopPosts({ posts }: Props) {
  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <h3 className="font-semibold mb-4">Top Posts</h3>
      <div className="space-y-2">
        {posts.slice(0, 8).map((p) => {
          const primary = p.reach ?? p.views ?? p.likes ?? 0;
          return (
            <div
              key={p.id}
              className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-muted transition-colors"
            >
              {platformBadge(p.platform)}
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{p.caption || "(no caption)"}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(p.published_at)}
                  {p.post_type && ` · ${p.post_type}`}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-semibold">{formatNumber(primary)}</p>
                <p className="text-[10px] text-muted-foreground">
                  {p.reach != null ? "reach" : p.views != null ? "views" : "likes"}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
