import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError, type RunResult } from "../lib/api";
import { faError } from "../lib/errors-fa";
import { faDigits, formatToman } from "../lib/money";

const STATUS_LABELS: Record<string, string> = {
  queued: "در صف",
  running: "در حال اجرا",
  waiting_approval: "در انتظار تأیید",
  completed: "انجام شد",
  failed: "ناموفق",
  cancelled: "لغو شد",
};

const STATUS_TONES: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-700",
  running: "bg-brand-50 text-brand-700",
  queued: "bg-slate-100 text-slate-600",
  waiting_approval: "bg-amber-50 text-amber-700",
  failed: "bg-rose-50 text-rose-700",
  cancelled: "bg-slate-100 text-slate-500",
};

function faTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("fa-IR");
}

/** Talk to one of your agents and read the history of everything you paid for. */
export default function Runs() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [agentId, setAgentId] = useState(params.get("agent") ?? "");
  const [input, setInput] = useState("");
  const [answer, setAnswer] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.runs(50) });

  const active = (agents.data ?? []).filter((agent) => agent.is_active);
  const selected = agentId || active[0]?.id || "";

  const send = useMutation({
    mutationFn: () => api.startRun(selected, input.trim()),
    onSuccess: async (result) => {
      setAnswer(result);
      setInput("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["runs"] });
      await queryClient.invalidateQueries({ queryKey: ["wallet"] });
    },
    onError: (err) => setError(faError((err as ApiError).code)),
  });

  const agentName = (id: string | null) =>
    (agents.data ?? []).find((agent) => agent.id === id)?.name ?? "ایجنت حذف‌شده";

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">گفتگوها</h1>
      </header>

      {active.length === 0 ? (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
          برای شروع، اول یک ایجنت فعال بسازید.
          <button className="mr-2 underline" onClick={() => navigate("/agents")}>
            ساخت ایجنت
          </button>
        </p>
      ) : (
        <section className="card space-y-3">
          <select
            className="input"
            value={selected}
            onChange={(event) => setAgentId(event.target.value)}
          >
            {active.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>

          <textarea
            className="input min-h-[96px] resize-y"
            placeholder="پیام خود را بنویسید…"
            maxLength={8000}
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />

          <button
            className="btn-primary w-full"
            disabled={send.isPending || input.trim().length === 0 || !selected}
            onClick={() => send.mutate()}
          >
            {send.isPending ? "در حال پردازش…" : "ارسال"}
          </button>

          {error ? (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>
          ) : null}
        </section>
      )}

      {answer ? (
        <section className="card space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">پاسخ</p>
            <span className="text-[11px] text-slate-400">
              هزینه: {formatToman(answer.run.cost_irr)}
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">
            {answer.text || "پاسخی برنگشت."}
          </p>
          <p className="text-[11px] text-slate-400">
            {faDigits(answer.run.tokens_in)} توکن ورودی · {faDigits(answer.run.tokens_out)} توکن
            خروجی
          </p>
        </section>
      ) : null}

      <section className="space-y-2">
        <p className="text-sm font-semibold">تاریخچه</p>

        {runs.isLoading ? (
          <p className="text-xs text-slate-400">در حال بارگذاری…</p>
        ) : runs.isError ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
            تاریخچه دریافت نشد. اتصال خود را بررسی کنید.
          </p>
        ) : (runs.data ?? []).length === 0 ? (
          <p className="text-xs text-slate-400">هنوز گفتگویی ثبت نشده است.</p>
        ) : (
          (runs.data ?? []).map((run) => (
            <article key={run.id} className="card flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{agentName(run.agent_id)}</p>
                <p className="text-xs text-slate-400">{faTime(run.created_at)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {formatToman(run.cost_irr)}
                  {run.tokens_in + run.tokens_out > 0
                    ? ` · ${faDigits(run.tokens_in + run.tokens_out)} توکن`
                    : ""}
                </p>
                {run.error_code ? (
                  <p className="mt-1 text-[11px] text-rose-700">{faError(run.error_code)}</p>
                ) : null}
              </div>
              <span
                className={`rounded-full px-2 py-1 text-[11px] ${
                  STATUS_TONES[run.status] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {STATUS_LABELS[run.status] ?? run.status}
              </span>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
