"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  FileText,
  Beaker,
  Users,
  Sparkles,
  Calendar,
  Link2,
  Settings,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/manager", label: "Manager", icon: MessageSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/posts", label: "Posts", icon: FileText },
  { href: "/experiments", label: "Experiments", icon: Beaker },
  { href: "/audience", label: "Audience", icon: Users },
  { href: "/opportunities", label: "Opportunities", icon: Sparkles },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/accounts", label: "Accounts", icon: Link2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-56 bg-sidebar-bg flex flex-col z-50">
      <div className="px-5 py-6">
        <h1 className="text-sidebar-active text-lg font-semibold tracking-tight">
          Kobby Manager
        </h1>
      </div>

      <nav className="flex-1 px-3 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-white/10 text-sidebar-active font-medium"
                  : "text-sidebar-text hover:text-sidebar-active hover:bg-white/5"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold">
            KC
          </div>
          <div>
            <p className="text-sidebar-active text-sm font-medium">@kobbycooper</p>
            <p className="text-sidebar-text text-xs">14,365 followers</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
