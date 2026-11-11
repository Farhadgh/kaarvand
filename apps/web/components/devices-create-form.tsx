"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { formatDateTime, toFaDigits } from "@/lib/format";
import type { DeviceWithCode } from "@/lib/types";

export function DeviceCreateForm({ canEdit }: { canEdit: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<{ device: string; code: string; expires: string } | null>(null);
  const [name, setName] = useState("");
  const [paths, setPaths] = useState("C:\\Users\\Public");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await clientFetch<DeviceWithCode>("/devices", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          os: "windows",
          allowed_paths: paths
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      });
      setCode({
        device: created.name,
        code: created.pairing_code,
        expires: created.pairing_expires_at,
      });
      setName("");
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
      {error ? <ErrorBox message={error} /> : null}
      {code ? (
        <div className="rounded-xl2 border border-brand-200 bg-brand-50 p-4">
          <p className="text-sm text-brand-900">
            دستگاه «{code.device}» ساخته شد؛ این کد را در کلاینت کانکتور وارد کنید:
          </p>
          <p className="mt-1 font-mono text-3xl tracking-[0.35em] text-brand-800" dir="ltr">
            {toFaDigits(code.code)}
          </p>
          <p className="mt-1 text-xs text-brand-700">
            اعتبار تا {formatDateTime(code.expires)}
          </p>
        </div>
      ) : null}

      <Card>
        <CardHeader title="افزودن دستگاه" subtitle="کد ۸ رقمی برای جفت‌سازی کلاینت" />
        <form className="card-body grid grid-cols-1 gap-4 md:grid-cols-3" onSubmit={submit}>
          <Field label="نام دستگاه">
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="لپ‌تاپ دفتر"
              required
            />
          </Field>
          <Field label="مسیرهای مجاز" hint="با کاما جدا کنید">
            <input
              className="input ltr"
              dir="ltr"
              value={paths}
              onChange={(event) => setPaths(event.target.value)}
            />
          </Field>
          <div className="flex items-end">
            <button className="btn-primary w-full" disabled={busy || !name.trim()}>
              {busy ? "…" : "ساخت دستگاه"}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
