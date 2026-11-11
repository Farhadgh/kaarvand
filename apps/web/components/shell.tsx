"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  Cpu,
  FileText,
  Home,
  LogOut,
  Menu,
  Mic,
  Monitor,
  Plug,
  Settings,
  Terminal,
  Users,
  Wrench,
  X,
} from "lucide-react";

import { nav, roles } from "@/lib/copy";
import { cn } from "@/lib/cn";
import type { Meta, User } from "@/lib/types";

const icons = {
  home: Home,
  terminal: Terminal,
  bot: Bot,
  plug: Plug,
  cpu: Cpu,
  fileText: FileText,
  mic: Mic,
  wrench: Wrench,
  monitor: Monitor,
  activity: Activity,
  chart: BarChart3,
  users: Users,
  settings: Settings,
} as const;

export function Shell({
  user,
  meta,
  children,
}: {
  user: User;
  meta: Meta | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  const items = nav.filter((item) => {
    if (user.role === "viewer") {
      return !["/users", "/settings"].includes(item.href);
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-ink-50 lg:grid lg:grid-cols-[16rem_1fr]">
      {/* sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-40 w-64 border-l border-ink-200 bg-white transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              ک
            </span>
            <span className="font-bold text-ink-900">کاروند</span>
          </Link>
          <button
            className="rounded-lg p-1 text-ink-500 lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="بستن منو"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex flex-col gap-1 p-3">
          {items.map((item) => {
            const Icon = icons[item.icon as keyof typeof icons] ?? Home;
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "bg-brand-50 font-medium text-brand-700"
                    : "text-ink-600 hover:bg-ink-50",
                )}
              >
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {meta?.free_mode ? (
          <div className="mx-3 mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
            حالت آزمایشی — بدون درگاه پرداخت
          </div>
        ) : null}
      </aside>

      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-200 bg-white/90 px-4 py-3 backdrop-blur lg:px-6">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg border border-ink-200 p-1.5 text-ink-600 lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="باز کردن منو"
            >
              <Menu size={18} />
            </button>
            <div className="text-sm text-ink-500">
              {meta ? `${meta.app_name} — نسخه ${meta.version}` : "کاروند"}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-left">
              <p className="text-sm font-medium text-ink-900">{user.full_name}</p>
              <p className="text-xs text-ink-500">{roles[user.role] ?? user.role}</p>
            </div>
            <button className="btn-ghost !px-2" onClick={logout} title="خروج">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
