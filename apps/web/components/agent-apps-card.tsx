"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppIcon } from "@/components/app-icons";
import { Badge, Card, CardHeader, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages, permissionLabels } from "@/lib/copy";
import type { CatalogApp, Tool, User } from "@/lib/types";

type Binding = { tool_id: string; permission_level: string; is_enabled: boolean };

/** Apps installed for this agent (tools that carry `config.app_slug`). */
export function AgentAppsCard({
  agentId,
  tools,
  bindings,
  catalog,
  me,
}: {
  agentId: string;
  tools: Tool[];
  bindings: Binding[];
  catalog: CatalogApp[];
  me: User;
}) {
  const router = useRouter();
  const canEdit = me.role === "admin";
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const byTool = new Map(bindings.map((binding) => [binding.tool_id, binding]));
  const byApp = new Map(catalog.map((app) => [app.slug, app]));
  const installed = tools.filter((tool) => Boolean(tool.config?.app_slug));

  async function uninstall(appSlug: string) {
    if (!window.confirm(messages.confirmDelete)) return;
    setBusy(appSlug);
    setError(null);
    try {
      await clientFetch(`/apps/${appSlug}/install?agent_id=${agentId}`, { method: "DELETE" });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="برنامه‌ها و شبکه‌ها"
        subtitle="واتساپ، تلگرام، آفیس و هر برنامه‌ای که برای این ایجنت وصل کرده‌اید"
        action={
          canEdit ? (
            <Link href="/apps" className="btn-ghost !py-1 text-xs">
              + افزودن برنامه
            </Link>
          ) : null
        }
      />
      <div className="card-body space-y-3">
        {error ? <ErrorBox message={error} /> : null}

        {installed.length === 0 ? (
          <p className="muted">
            هنوز برنامه‌ای متصل نیست. از بخش{" "}
            <Link href="/apps" className="text-brand-700 underline">
              برنامه‌ها
            </Link>{" "}
            واتساپ، تلگرام، اکسل یا ابزار دلخواه را اضافه کنید.
          </p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {installed.map((tool) => {
              const binding = byTool.get(tool.id);
              const appSlug = String(tool.config?.app_slug);
              return (
                <li
                  key={tool.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-2.5"
                >
                  <div className="flex items-center gap-2">
                    <AppIcon
                      icon={byApp.get(appSlug)?.icon}
                      color={byApp.get(appSlug)?.color}
                      name={tool.name_fa}
                      size={16}
                    />
                    <div>
                      <p className="font-medium text-ink-900">{tool.name_fa}</p>
                      <p className="ltr text-[11px] text-ink-400">{tool.slug}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      value={binding?.permission_level ?? tool.approval_policy}
                      label={
                        permissionLabels[binding?.permission_level ?? tool.approval_policy] ??
                        tool.approval_policy
                      }
                    />
                    <Link
                      href="/tools"
                      className="btn-ghost !px-2 !py-1 text-xs"
                      title="تست و ویرایش در صفحه‌ی ابزارها"
                    >
                      جزئیات
                    </Link>
                    {canEdit ? (
                      <button
                        className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
                        disabled={busy === appSlug}
                        onClick={() => void uninstall(appSlug)}
                      >
                        {busy === appSlug ? "…" : "قطع اتصال"}
                      </button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}
