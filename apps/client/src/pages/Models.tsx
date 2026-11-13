import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type CatalogModel } from "../lib/api";
import { faDigits, formatTomanValue } from "../lib/money";

const FILTERS = [
  { key: "", label: "همه" },
  { key: "tools", label: "ابزار" },
  { key: "vision", label: "تصویر" },
  { key: "audio", label: "صدا" },
  { key: "reasoning", label: "استدلال" },
];

const CAPABILITY_LABELS: Record<string, string> = {
  tools: "ابزار",
  vision: "تصویر",
  audio: "صدا",
  reasoning: "استدلال",
  stream: "استریم",
};

const PERSIAN_LABELS: Record<string, string> = {
  verified: "فارسی: تأییدشده",
  good: "فارسی: خوب",
  weak: "فارسی: ضعیف",
  none: "فارسی: ندارد",
};

function priceLines(model: CatalogModel): string[] {
  if (model.billing_unit === "per_minute") {
    return model.price_audio_minute_toman === null
      ? []
      : [`${formatTomanValue(model.price_audio_minute_toman)} برای هر دقیقه`];
  }
  if (model.billing_unit === "per_1k_chars") {
    return model.price_audio_1k_chars_toman === null
      ? []
      : [`${formatTomanValue(model.price_audio_1k_chars_toman)} برای هر ۱۰۰۰ کاراکتر`];
  }
  const lines: string[] = [];
  if (model.price_input_toman !== null) {
    lines.push(`ورودی: ${formatTomanValue(model.price_input_toman)} / میلیون توکن`);
  }
  if (model.price_output_toman !== null) {
    lines.push(`خروجی: ${formatTomanValue(model.price_output_toman)} / میلیون توکن`);
  }
  return lines;
}

/** Customer model picker: Persian names and Toman prices, nothing else. */
export default function Models() {
  const navigate = useNavigate();
  const [capability, setCapability] = useState("");
  const [search, setSearch] = useState("");

  const models = useQuery({
    queryKey: ["catalog", capability, search],
    queryFn: () => api.catalog({ capability: capability || undefined, q: search || undefined }),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">مدل‌ها</h1>
      </header>

      <input
        className="input"
        placeholder="جست‌وجوی مدل…"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <button
            key={filter.key}
            className={`rounded-full border px-3 py-1 text-xs ${
              capability === filter.key
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-200 bg-white text-slate-600"
            }`}
            onClick={() => setCapability(filter.key)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {models.isLoading ? (
        <p className="text-xs text-slate-400">در حال بارگذاری…</p>
      ) : models.isError ? (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
          فهرست مدل‌ها دریافت نشد. اتصال خود را بررسی کنید.
        </p>
      ) : (models.data ?? []).length === 0 ? (
        <p className="text-xs text-slate-400">مدلی با این فیلتر پیدا نشد.</p>
      ) : (
        <div className="space-y-2">
          {(models.data ?? []).map((model) => {
            const lines = priceLines(model);
            return (
              <article key={model.id} className="card space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold">{model.name}</p>
                    <p className="text-xs text-slate-400">
                      {model.family ?? "مدل زبانی"}
                      {model.context_window
                        ? ` · پنجرهٔ ${faDigits(model.context_window.toLocaleString("en-US"))} توکن`
                        : ""}
                    </p>
                  </div>
                  {model.persian ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
                      {PERSIAN_LABELS[model.persian] ?? model.persian}
                    </span>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-1">
                  {model.capabilities
                    .filter((item) => item !== "stream")
                    .map((item) => (
                      <span
                        key={item}
                        className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
                      >
                        {CAPABILITY_LABELS[item] ?? item}
                      </span>
                    ))}
                  {model.audio_kind ? (
                    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] text-brand-700">
                      {model.audio_kind === "stt" ? "گفتار به متن" : "متن به گفتار"}
                    </span>
                  ) : null}
                </div>

                {lines.length > 0 ? (
                  <ul className="space-y-0.5 text-xs text-slate-600">
                    {lines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-400">قیمت این مدل به‌زودی اعلام می‌شود.</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
