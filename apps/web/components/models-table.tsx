"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/format";
import type { Model } from "@/lib/types";

type Probe = { text: string; tokens_in: number; tokens_out: number; cost_irr: number };

export function ModelsTable({
  models,
  providerNames,
  canEdit,
}: {
  models: Model[];
  providerNames: Record<string, string>;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [capability, setCapability] = useState("");
  const [probe, setProbe] = useState<{ model: string; result: Probe } | null>(null);

  const filtered = models.filter((model) => {
    const haystack = `${model.external_id} ${model.display_name_fa ?? ""}`.toLowerCase();
    if (query && !haystack.includes(query.toLowerCase())) return false;
    if (capability && !model[`supports_${capability}` as keyof Model]) return false;
    return true;
  });

  async function act(key: string, task: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await task();
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function runProbe(model: Model) {
    setBusy(`probe-${model.id}`);
    setError(null);
    setProbe(null);
    try {
      const result = await clientFetch<Probe>(`/models/${model.id}/probe`, {
        method: "POST",
        body: JSON.stringify({ prompt: "خودت را در یک جمله معرفی کن.", max_tokens: 64 }),
      });
      setProbe({ model: model.external_id, result });
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {error ? <ErrorBox message={error} /> : null}
      {probe ? (
        <div className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900">
          <div className="font-medium">پاسخ {probe.model}</div>
          <p className="mt-1 whitespace-pre-wrap">{probe.result.text}</p>
          <p className="mt-1 text-xs text-brand-700">
            {formatNumber(probe.result.tokens_in)} ورودی · {formatNumber(probe.result.tokens_out)}{" "}
            خروجی · {formatMoney(probe.result.cost_irr)}
          </p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <input
          className="input w-64"
          placeholder="جست‌وجوی مدل…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="input w-48"
          value={capability}
          onChange={(event) => setCapability(event.target.value)}
        >
          <option value="">همه‌ی قابلیت‌ها</option>
          <option value="tools">فراخوانی ابزار</option>
          <option value="vision">بینایی</option>
          <option value="reasoning">استدلال</option>
        </select>
        <span className="muted">{formatNumber(filtered.length)} مدل</span>
      </div>

      <div className="table-wrapper">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">مدل</th>
              <th className="th">پروایدر</th>
              <th className="th">قابلیت</th>
              <th className="th">ورودی</th>
              <th className="th">خروجی</th>
              <th className="th">وضعیت</th>
              <th className="th">آزمایش</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td className="td text-center text-ink-500" colSpan={7}>
                  مدلی یافت نشد. ابتدا پروایدر را سینک کنید.
                </td>
              </tr>
            ) : (
              filtered.slice(0, 200).map((model) => (
                <tr key={model.id} className="hover:bg-ink-50/60">
                  <td className="td">
                    <div className="font-medium text-ink-900" dir="ltr">
                      {model.external_id}
                    </div>
                    <div className="text-xs text-ink-400">
                      {model.display_name_fa ?? model.family ?? "—"}
                    </div>
                  </td>
                  <td className="td text-xs">{providerNames[model.provider_id] ?? "—"}</td>
                  <td className="td">
                    <div className="flex flex-wrap gap-1">
                      {model.supports_tools ? <Badge value="low" label="ابزار" /> : null}
                      {model.supports_vision ? <Badge value="low" label="بینایی" /> : null}
                      {model.supports_reasoning ? <Badge value="low" label="استدلال" /> : null}
                    </div>
                  </td>
                  <td className="td ltr text-xs">{model.input_price ?? "—"}</td>
                  <td className="td ltr text-xs">{model.output_price ?? "—"}</td>
                  <td className="td">
                    <button
                      className="btn-ghost !px-2 !py-1 text-xs"
                      disabled={!canEdit || busy === model.id}
                      onClick={() =>
                        void act(model.id, () =>
                          clientFetch(`/models/${model.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ is_enabled: !model.is_enabled }),
                          }),
                        )
                      }
                    >
                      {model.is_enabled ? "فعال" : "غیرفعال"}
                    </button>
                  </td>
                  <td className="td">
                    <button
                      className="btn-ghost !px-2 !py-1 text-xs"
                      disabled={!canEdit || busy === `probe-${model.id}`}
                      onClick={() => void runProbe(model)}
                    >
                      {busy === `probe-${model.id}` ? "…" : "اجرا"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
