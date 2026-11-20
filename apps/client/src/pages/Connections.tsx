import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError, type Channel } from "../lib/api";
import { faError } from "../lib/errors-fa";
import { faDigits } from "../lib/money";

const PROVIDERS: Record<string, string> = {
  telegram: "تلگرام",
  whatsapp: "واتس‌اپ",
};

/** Messenger and webhook connections: one channel answers with one agent. */
export default function Connections() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<"telegram" | "whatsapp">("telegram");
  const [agentId, setAgentId] = useState("");
  const [replyMode, setReplyMode] = useState<"off" | "auto">("auto");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const channels = useQuery({ queryKey: ["channels"], queryFn: api.channels });
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents });
  const active = (agents.data ?? []).filter((agent) => agent.is_active);
  const selectedAgent = agentId || active[0]?.id || "";

  function fail(err: unknown) {
    setError(faError((err as ApiError).code));
  }

  const create = useMutation({
    mutationFn: () =>
      api.createChannel({
        name_fa: name.trim(),
        provider,
        agent_id: selectedAgent,
        reply_mode: replyMode,
      }),
    onSuccess: async () => {
      setName("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
    onError: fail,
  });

  const remove = useMutation({
    mutationFn: (channel: Channel) => api.deleteChannel(channel.id),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
    onError: fail,
  });

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setError("کپی نشد؛ آدرس را دستی انتخاب کنید.");
    }
  }

  const agentName = (id: string) =>
    (agents.data ?? []).find((agent) => agent.id === id)?.name ?? "ایجنت حذف‌شده";

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">اتصال‌ها</h1>
      </header>

      <p className="rounded-xl bg-slate-100 px-3 py-2 text-xs text-slate-600">
        هر اتصال یک ایجنت را به یک پیام‌رسان وصل می‌کند. آدرس وبهوک را در پنل پیام‌رسان ثبت کنید تا
        پیام‌های مشتریان به ایجنت برسد.
      </p>

      {active.length === 0 ? (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
          برای ساخت اتصال، اول یک ایجنت فعال بسازید.
          <button className="mr-2 underline" onClick={() => navigate("/agents")}>
            ساخت ایجنت
          </button>
        </p>
      ) : (
        <section className="card space-y-3">
          <p className="text-sm font-semibold">اتصال تازه</p>

          <input
            className="input"
            placeholder="نام اتصال (مثلاً پشتیبانی تلگرام)"
            value={name}
            maxLength={160}
            onChange={(event) => setName(event.target.value)}
          />

          <div className="grid grid-cols-2 gap-2">
            <select
              className="input"
              value={provider}
              onChange={(event) => setProvider(event.target.value as "telegram" | "whatsapp")}
            >
              <option value="telegram">تلگرام</option>
              <option value="whatsapp">واتس‌اپ</option>
            </select>

            <select
              className="input"
              value={replyMode}
              onChange={(event) => setReplyMode(event.target.value as "off" | "auto")}
            >
              <option value="auto">پاسخ خودکار</option>
              <option value="off">فقط دریافت پیام</option>
            </select>
          </div>

          <select
            className="input"
            value={selectedAgent}
            onChange={(event) => setAgentId(event.target.value)}
          >
            {active.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>

          <button
            className="btn-primary w-full"
            disabled={create.isPending || name.trim().length === 0 || !selectedAgent}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "در حال ساخت…" : "ساخت اتصال"}
          </button>

          {error ? (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>
          ) : null}
        </section>
      )}

      <section className="space-y-2">
        <p className="text-sm font-semibold">اتصال‌های من</p>

        {channels.isLoading ? (
          <p className="text-xs text-slate-400">در حال بارگذاری…</p>
        ) : channels.isError ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
            فهرست اتصال‌ها دریافت نشد. اتصال خود را بررسی کنید.
          </p>
        ) : (channels.data ?? []).length === 0 ? (
          <p className="text-xs text-slate-400">هنوز اتصالی نساخته‌اید.</p>
        ) : (
          (channels.data ?? []).map((channel) => (
            <article key={channel.id} className="card space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">{channel.name_fa}</p>
                  <p className="text-xs text-slate-400">
                    {PROVIDERS[channel.provider] ?? channel.provider} · {agentName(channel.agent_id)}
                    {channel.reply_mode === "auto" ? " · پاسخ خودکار" : ""}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-1 text-[11px] ${
                    channel.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {channel.is_active ? "فعال" : "غیرفعال"}
                </span>
              </div>

              <div className="space-y-1">
                <p className="text-[11px] text-slate-500">آدرس وبهوک</p>
                <p dir="ltr" className="break-all rounded-xl bg-slate-50 px-3 py-2 text-[11px] text-slate-700">
                  {channel.webhook_url || "—"}
                </p>
                <p className="text-[11px] text-slate-400">
                  {faDigits(channel.events_count)} پیام دریافت‌شده
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-ghost px-3 py-1.5 text-xs"
                  disabled={!channel.webhook_url}
                  onClick={() => void copy(channel.webhook_url)}
                >
                  {copied === channel.webhook_url ? "کپی شد" : "کپی آدرس"}
                </button>
                <button
                  className="btn-ghost px-3 py-1.5 text-xs text-rose-700"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (window.confirm(`اتصال «${channel.name_fa}» حذف شود؟`))
                      remove.mutate(channel);
                  }}
                >
                  حذف
                </button>
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
