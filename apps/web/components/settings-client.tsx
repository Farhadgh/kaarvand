"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { SettingsPayload } from "@/lib/types";

export function SettingsClient({
  settings,
  canEdit,
}: {
  settings: SettingsPayload;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [org, setOrg] = useState({
    name: settings.org.name,
    timezone: settings.org.timezone,
    digits: settings.org.digits,
    tax_rate: String(settings.org.tax_rate),
    invoice_prefix: settings.org.invoice_prefix,
    monthly_budget_irr: settings.org.monthly_budget_irr
      ? String(settings.org.monthly_budget_irr)
      : "",
  });
  const [fx, setFx] = useState(String(settings.fx.usd_irr));
  const [me, setMe] = useState({
    full_name: settings.me.full_name,
    digits_pref: settings.me.digits_pref,
  });

  async function act(key: string, task: () => Promise<unknown>, success: string) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await task();
      setNotice(success);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      {error ? <ErrorBox message={error} /> : null}
      {notice ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      <Card>
        <CardHeader title="سازمان" subtitle="نام، منطقه‌ی زمانی، ارقام و مالیات" />
        <form
          className="card-body grid grid-cols-1 gap-4 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            void act(
              "org",
              () =>
                clientFetch("/settings/org", {
                  method: "PATCH",
                  body: JSON.stringify({
                    name: org.name,
                    timezone: org.timezone,
                    digits: org.digits,
                    tax_rate: org.tax_rate,
                    invoice_prefix: org.invoice_prefix,
                    monthly_budget_irr: org.monthly_budget_irr
                      ? Number(org.monthly_budget_irr)
                      : null,
                  }),
                }),
              "تنظیمات سازمان ذخیره شد.",
            );
          }}
        >
          <Field label="نام سازمان">
            <input
              className="input"
              value={org.name}
              disabled={!canEdit}
              onChange={(event) => setOrg({ ...org, name: event.target.value })}
            />
          </Field>
          <Field label="منطقه‌ی زمانی">
            <input
              className="input ltr"
              dir="ltr"
              value={org.timezone}
              disabled={!canEdit}
              onChange={(event) => setOrg({ ...org, timezone: event.target.value })}
            />
          </Field>
          <Field label="ارقام">
            <select
              className="input"
              value={org.digits}
              disabled={!canEdit}
              onChange={(event) => setOrg({ ...org, digits: event.target.value })}
            >
              <option value="fa">فارسی (۱۲۳)</option>
              <option value="en">لاتین (123)</option>
            </select>
          </Field>
          <Field label="مالیات (٪)">
            <input
              className="input ltr"
              dir="ltr"
              value={org.tax_rate}
              disabled={!canEdit}
              onChange={(event) => setOrg({ ...org, tax_rate: event.target.value })}
            />
          </Field>
          <Field label="پیش‌شماره‌ی فاکتور">
            <input
              className="input ltr"
              dir="ltr"
              value={org.invoice_prefix}
              disabled={!canEdit}
              onChange={(event) => setOrg({ ...org, invoice_prefix: event.target.value })}
            />
          </Field>
          <Field label="سقف بودجه‌ی ماهانه (ریال)" hint="خالی = بدون سقف">
            <input
              className="input ltr"
              dir="ltr"
              value={org.monthly_budget_irr}
              disabled={!canEdit}
              onChange={(event) =>
                setOrg({ ...org, monthly_budget_irr: event.target.value.replace(/\D/g, "") })
              }
            />
          </Field>
          <div className="flex items-end justify-end md:col-span-2">
            <button className="btn-primary" disabled={!canEdit || busy === "org"}>
              {busy === "org" ? "…" : messages.save}
            </button>
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader title="نرخ ارز" subtitle="همه‌ی هزینه‌های آینده از این نرخ استفاده می‌کنند" />
        <form
          className="card-body flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void act(
              "fx",
              () =>
                clientFetch("/settings/fx", {
                  method: "PATCH",
                  body: JSON.stringify({ usd_irr: Number(fx || 0) }),
                }),
              "نرخ ارز به‌روزرسانی شد.",
            );
          }}
        >
          <div className="w-56">
            <Field label="هر دلار (ریال)">
              <input
                className="input ltr"
                dir="ltr"
                value={fx}
                disabled={!canEdit}
                onChange={(event) => setFx(event.target.value.replace(/\D/g, ""))}
              />
            </Field>
          </div>
          <button className="btn-primary" disabled={!canEdit || busy === "fx"}>
            {busy === "fx" ? "…" : messages.save}
          </button>
          <p className="muted">منبع: {settings.fx.source}</p>
        </form>
      </Card>

      <Card>
        <CardHeader title="پروفایل من" subtitle="نام نمایشی و شکل ارقام" />
        <form
          className="card-body grid grid-cols-1 gap-4 md:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            void act(
              "me",
              () =>
                clientFetch("/settings/me", {
                  method: "PATCH",
                  body: JSON.stringify(me),
                }),
              "پروفایل ذخیره شد.",
            );
          }}
        >
          <Field label="نام نمایشی">
            <input
              className="input"
              value={me.full_name}
              onChange={(event) => setMe({ ...me, full_name: event.target.value })}
            />
          </Field>
          <Field label="ارقام">
            <select
              className="input"
              value={me.digits_pref}
              onChange={(event) => setMe({ ...me, digits_pref: event.target.value as "fa" | "en" })}
            >
              <option value="fa">فارسی</option>
              <option value="en">لاتین</option>
            </select>
          </Field>
          <div className="flex items-end">
            <button className="btn-primary" disabled={busy === "me"}>
              {busy === "me" ? "…" : messages.save}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
