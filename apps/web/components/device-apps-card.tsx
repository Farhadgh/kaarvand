"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppIcon } from "@/components/app-icons";
import { Badge, Card, CardHeader, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import type { Device, DeviceApp } from "@/lib/types";

export function DeviceAppsCard({
  device,
  apps,
  canEdit,
}: {
  device: Device;
  apps: DeviceApp[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);

  async function scan() {
    setBusy(true);
    setError(null);
    setScanNote(null);
    try {
      const result = await clientFetch<{ found: number }>(
        `/devices/${device.id}/scan-apps`,
        { method: "POST" },
      );
      setScanNote(`${result.found} برنامه‌ی شناخته‌شده روی این دستگاه پیدا شد.`);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(app: DeviceApp) {
    setBusy(true);
    setError(null);
    try {
      await clientFetch(`/devices/${device.id}/apps/${app.app_slug}`, {
        method: "PATCH",
        body: JSON.stringify({ is_granted: !app.is_granted }),
      });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title={`برنامه‌های ${device.name}`}
        subtitle="برنامه‌های نصب‌شده را شناسایی و مجاز کنید"
        action={
          canEdit ? (
            <button className="btn-ghost !py-1 text-xs" onClick={() => void scan()} disabled={busy}>
              {busy ? "…" : "اسکن برنامه‌ها"}
            </button>
          ) : null
        }
      />
      <div className="card-body space-y-3">
        {error ? <ErrorBox message={error} /> : null}
        {scanNote ? <p className="text-xs text-emerald-700">{scanNote}</p> : null}

        {apps.length === 0 ? (
          <p className="muted">
            هنوز برنامه‌ای شناسایی نشده است؛ کانکتور را اجرا کنید و «اسکن برنامه‌ها» را بزنید.
          </p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {apps.map((app) => (
              <li
                key={app.app_slug}
                className="flex flex-wrap items-center justify-between gap-3 py-2.5"
              >
                <div className="flex items-center gap-2">
                  <AppIcon icon={app.icon} color={app.color} name={app.name_fa ?? app.app_slug} size={18} />
                  <div>
                    <p className="font-medium text-ink-900">
                      {app.name_fa ?? app.app_slug}
                    </p>
                    <p className="ltr text-[11px] text-ink-400">
                      {app.exe ?? app.prog_id ?? "—"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    value={app.is_granted ? "online" : "pending"}
                    label={app.is_granted ? "مجاز" : "غیرمجاز"}
                  />
                  {canEdit ? (
                    <button
                      className="btn-ghost !px-2 !py-1 text-xs"
                      onClick={() => void toggle(app)}
                      disabled={busy}
                    >
                      {app.is_granted ? "لغو مجوز" : "مجاز کن"}
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
