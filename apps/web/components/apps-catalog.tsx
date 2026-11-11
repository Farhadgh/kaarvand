"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { AppIcon, AppTile } from "@/components/app-icons";
import { AppInstallWizard } from "@/components/app-install-wizard";
import { CustomToolForm } from "@/components/custom-tool-form";
import { Badge, Card, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { runtimeLabels } from "@/lib/copy";
import type { CatalogApp, CatalogAppDetail, Device } from "@/lib/types";

type AgentOption = { id: string; name: string };

const tabs: { key: string; label: string }[] = [
  { key: "", label: "همه" },
  { key: "social", label: "شبکه‌های اجتماعی" },
  { key: "office", label: "آفیس و ایمیل" },
  { key: "productivity", label: "بهره‌وری" },
  { key: "devices", label: "برنامه‌های ویندوز" },
];

export function AppsCatalog({
  apps,
  agents,
  devices,
  canEdit,
}: {
  apps: CatalogApp[];
  agents: AgentOption[];
  devices: Device[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [tab, setTab] = useState("");
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState<CatalogAppDetail | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customOpen, setCustomOpen] = useState(false);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return apps.filter((app) => {
      if (tab && app.category !== tab) return false;
      if (!needle) return true;
      return [app.name_fa, app.name_en ?? "", app.slug, app.vendor ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [apps, tab, query]);

  async function open(app: CatalogApp) {
    setBusySlug(app.slug);
    setError(null);
    try {
      setDetail(await clientFetch<CatalogAppDetail>(`/apps/${app.slug}`));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusySlug(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorBox message={error} /> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {tabs.map((item) => (
            <button
              key={item.key || "all"}
              className={`btn-ghost !px-3 !py-1.5 text-xs ${
                tab === item.key ? "!border-brand-400 !text-brand-700" : ""
              }`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <input
            className="input w-52"
            placeholder="جست‌وجوی برنامه…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {canEdit ? (
            <button className="btn-primary" onClick={() => setCustomOpen(true)}>
              + افزودن ابزار من
            </button>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((app) => (
          <Card key={app.slug} className="flex flex-col">
            <div className="card-body flex flex-1 flex-col gap-3">
              <div className="flex items-start gap-3">
                <AppTile icon={app.icon} color={app.color} name={app.name_fa} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-bold text-ink-900">{app.name_fa}</h3>
                    <Badge
                      value={app.runtime === "desktop" ? "pending" : "online"}
                      label={runtimeLabels[app.runtime] ?? app.runtime}
                    />
                  </div>
                  <p className="ltr text-xs text-ink-400">{app.name_en ?? app.slug}</p>
                </div>
              </div>

              <p className="text-sm text-ink-600">{app.description_fa ?? "—"}</p>

              <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                <Badge value={app.risk_level} />
                {app.installed_agents > 0 ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700">
                    متصل به {app.installed_agents} ایجنت
                  </span>
                ) : null}
                {app.detected_devices > 0 ? (
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-brand-700">
                    روی {app.detected_devices} دستگاه
                  </span>
                ) : null}
              </div>

              <div className="mt-auto flex items-center justify-between gap-2">
                {app.docs_url ? (
                  <a
                    className="text-xs text-ink-400 underline-offset-2 hover:underline"
                    href={app.docs_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    مستندات
                  </a>
                ) : (
                  <span />
                )}
                <button
                  className="btn-primary !py-1 text-xs"
                  disabled={!canEdit || busySlug === app.slug}
                  onClick={() => void open(app)}
                >
                  {busySlug === app.slug
                    ? "…"
                    : app.installed_agents > 0
                      ? "اتصال جدید"
                      : "اتصال"}
                </button>
              </div>
            </div>
          </Card>
        ))}

        {canEdit ? (
          <button
            className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-xl2 border-2 border-dashed border-ink-200 p-6 text-ink-500 transition hover:border-brand-300 hover:text-brand-700"
            onClick={() => setCustomOpen(true)}
          >
            <AppIcon icon="lucide:app-window" size={26} />
            <span className="text-sm font-medium">افزودن ابزار من</span>
            <span className="text-xs">HTTP سفارشی یا اسکریپت روی دستگاه</span>
          </button>
        ) : null}
      </div>

      {filtered.length === 0 ? (
        <p className="muted py-8 text-center">برنامه‌ای با این فیلتر پیدا نشد.</p>
      ) : null}

      <AppInstallWizard
        app={detail}
        agents={agents}
        devices={devices}
        onClose={() => setDetail(null)}
        onInstalled={() => router.refresh()}
      />

      {customOpen ? (
        <CustomToolForm
          onClose={() => setCustomOpen(false)}
          onCreated={() => {
            router.refresh();
            setCustomOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
