interface StatCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  icon?: React.ReactNode;
  color?: string;
}

export function StatCard({ label, value, sublabel, icon, color }: StatCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-muted-foreground text-xs font-medium uppercase tracking-wider">
          {label}
        </span>
        {icon && <span className={color || "text-muted-foreground"}>{icon}</span>}
      </div>
      <p className="text-2xl font-bold tracking-tight">{value}</p>
      {sublabel && (
        <p className="text-muted-foreground text-sm mt-1">{sublabel}</p>
      )}
    </div>
  );
}
