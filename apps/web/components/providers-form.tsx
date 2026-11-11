"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { Provider, ProviderAdapter } from "@/lib/types";

export function ProviderForm({
  adapters,
  canEdit,
}: {
  adapters: ProviderAdapter[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [kind, setKind] = useState(adapters[0]?.kind ?? "openai_compatible");
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await clientFetch<Provider>("/providers", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim() || adapters.find((item) => item.kind === kind)?.title_fa || kind,
          kind,
          base_url: baseUrl.trim() || null,
          api_key: apiKey.trim() || null,
        }),
      });
      setNotice("پروایدر ساخته شد. از جدول، «تست» و سپس «سینک مدل» را بزنید.");
      setName("");
      setBaseUrl("");
      setApiKey("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  if (!canEdit) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button className="btn-primary" onClick={() => setOpen((value) => !value)}>
          {open ? "بستن فرم" : "افزودن پروایدر"}
        </button>
      </div>

      {error ? <ErrorBox message={error} /> : null}
      {notice ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      {open ? (
        <Card>
          <CardHeader title="پروایدر جدید" subtitle="آدرس و کلید؛ بقیه خودکار" />
          <form className="card-body grid grid-cols-1 gap-4 md:grid-cols-2" onSubmit={submit}>
            <Field label="نوع پروایدر">
              <select className="input" value={kind} onChange={(event) => setKind(event.target.value)}>
                {adapters.map((adapter) => (
                  <option key={adapter.kind} value={adapter.kind}>
                    {adapter.title_fa}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="نام نمایشی" hint="خالی بگذارید تا از عنوان آداپتور استفاده شود">
              <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
            </Field>

            <Field label="آدرس پایه" hint="مثال: https://openrouter.ai/api/v1">
              <input
                className="input ltr"
                dir="ltr"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
              />
            </Field>

            <Field label="کلید API" hint="رمزنگاری‌شده ذخیره می‌شود و هرگز نمایش داده نمی‌شود">
              <input
                className="input ltr"
                dir="ltr"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </Field>

            <div className="flex justify-end gap-2 md:col-span-2">
              <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
                {messages.cancel}
              </button>
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "در حال ساخت…" : messages.create}
              </button>
            </div>
          </form>
        </Card>
      ) : null}
    </div>
  );
}
