"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import type {
  InboundChannel,
  InboundEvent,
  InboundTestResult,
  WebhookRegisterResult,
} from "@/lib/types";

type Option = { id: string; name: string };
type ToolOption = { id: string; label: string; appSlug: string };

export function ChannelsClient({
  channels,
  agents,
  replyTools,
  canEdit,
  apiBase,
}: {
  channels: InboundChannel[];
  agents: Option[];
  replyTools: ToolOption[];
  canEdit: boolean;
  apiBase: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState("telegram");
  const [nameFa, setNameFa] = useState("");
  const [agentId, setAgentId] = useState(agents[0]?.id ?? "");
  const [toolId, setToolId] = useState("");
  const [replyMode, setReplyMode] = useState("off");
  const [secret, setSecret] = useState("");
  const [verifyToken, setVerifyToken] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<Record<string, InboundEvent[]>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [tests, setTests] = useState<Record<string, InboundTestResult>>({});
  const [hooks, setHooks] = useState<Record<string, WebhookRegisterResult>>({});

  const matchingTools = replyTools.filter((tool) => tool.appSlug.startsWith(provider));

  async function create() {
    setBusy("create");
    setError(null);
    try {
      await clientFetch<InboundChannel>("/channels", {
        method: "POST",
        body: JSON.stringify({
          name_fa: nameFa.trim() || `کانال ${provider}`,
          provider,
          agent_id: agentId,
          tool_id: toolId || null,
          reply_mode: replyMode,
          verify_secret: secret.trim(),
          verify_token: provider === "whatsapp" ? verifyToken.trim() : null,
        }),
      });
      setOpen(false);
      setNameFa("");
      setSecret("");
      setVerifyToken("");
      setToolId("");
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

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

  async function loadEvents(channel: InboundChannel) {
    if (events[channel.id]) {
      setEvents((prev) => {
        const next = { ...prev };
        delete next[channel.id];
        return next;
      });
      return;
    }
    setBusy(`ev-${channel.id}`);
    try {
      const rows = await clientFetch<InboundEvent[]>(`/channels/${channel.id}/events`);
      setEvents((prev) => ({ ...prev, [channel.id]: rows }));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setCopied(null);
    }
  }

  async function runTest(channel: InboundChannel) {
    setBusy(`test-${channel.id}`);
    setError(null);
    try {
      const result = await clientFetch<InboundTestResult>(`/channels/${channel.id}/test`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setTests((prev) => ({ ...prev, [channel.id]: result }));
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function registerWebhook(channel: InboundChannel) {
    setBusy(`hook-${channel.id}`);
    setError(null);
    try {
      const result = await clientFetch<WebhookRegisterResult>(
        `/channels/${channel.id}/register-webhook`,
        { method: "POST" },
      );
      setHooks((prev) => ({ ...prev, [channel.id]: result }));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorBox message={error} /> : null}

      {canEdit ? (
        <Card>
          <CardHeader
            title="کانال جدید"
            subtitle="پس از ساخت، آدرس وبهوک را در پنل تلگرام/متا ثبت کنید"
            action={
              <button className="btn-ghost !py-1 text-xs" onClick={() => setOpen(!open)}>
                {open ? "بستن" : "+ کانال جدید"}
              </button>
            }
          />
          {open ? (
            <div className="card-body space-y-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="نام">
                  <input
                    className="input"
                    value={nameFa}
                    onChange={(event) => setNameFa(event.target.value)}
                    placeholder="مثلاً پشتیبانی واتساپ"
                  />
                </Field>
                <Field label="پیام‌رسان">
                  <select
                    className="input"
                    value={provider}
                    onChange={(event) => {
                      setProvider(event.target.value);
                      setToolId("");
                    }}
                  >
                    <option value="telegram">تلگرام</option>
                    <option value="whatsapp">واتساپ (Cloud API)</option>
                  </select>
                </Field>
                <Field label="ایجنت">
                  <select
                    className="input"
                    value={agentId}
                    onChange={(event) => setAgentId(event.target.value)}
                  >
                    <option value="">— انتخاب ایجنت —</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="ابزار پاسخ" hint="پاسخ ایجنت از طریق این ابزار ارسال می‌شود">
                  <select
                    className="input"
                    value={toolId}
                    onChange={(event) => setToolId(event.target.value)}
                  >
                    <option value="">— بدون پاسخ خودکار —</option>
                    {matchingTools.map((tool) => (
                      <option key={tool.id} value={tool.id}>
                        {tool.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="حالت پاسخ">
                  <select
                    className="input"
                    value={replyMode}
                    onChange={(event) => setReplyMode(event.target.value)}
                  >
                    <option value="off">فقط ثبت و اجرا (بدون ارسال)</option>
                    <option value="auto">ارسال خودکار پاسخ</option>
                  </select>
                </Field>
                <Field
                  label={provider === "telegram" ? "Secret Token وبهوک" : "App Secret (HMAC)"}
                  hint={
                    provider === "telegram"
                      ? "همان مقدار secret_token در setWebhook"
                      : "برای بررسی امضای X-Hub-Signature-256"
                  }
                >
                  <input
                    className="input ltr"
                    dir="ltr"
                    type="password"
                    autoComplete="off"
                    value={secret}
                    onChange={(event) => setSecret(event.target.value)}
                  />
                </Field>
                {provider === "whatsapp" ? (
                  <Field label="Verify Token" hint="مقدار hub.verify_token برای تأیید اولیه">
                    <input
                      className="input ltr"
                      dir="ltr"
                      value={verifyToken}
                      onChange={(event) => setVerifyToken(event.target.value)}
                    />
                  </Field>
                ) : null}
              </div>
              <div className="flex justify-end">
                <button
                  className="btn-primary"
                  onClick={() => void create()}
                  disabled={busy === "create" || !agentId || !secret.trim()}
                >
                  {busy === "create" ? "در حال ساخت…" : "ساخت کانال"}
                </button>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}

      {channels.length === 0 ? (
        <Card>
          <div className="card-body muted">
            هنوز کانالی ساخته نشده است. یک کانال بسازید، آدرس وبهوک را در پنل تلگرام/متا ثبت کنید
            و از سمت کاربر پیام بفرستید.
          </div>
        </Card>
      ) : null}

      {channels.map((channel) => {
        const url = channel.webhook_url || `${apiBase}${channel.webhook_path}`;
        const isWhatsApp = channel.provider === "whatsapp";
        const test = tests[channel.id];
        const hook = hooks[channel.id];
        return (
          <Card key={channel.id}>
            <CardHeader
              title={channel.name_fa}
              subtitle={`${channel.provider} · ${channel.slug}`}
              action={
                <div className="flex items-center gap-1">
                  <Badge
                    value={channel.is_active ? "online" : "offline"}
                    label={channel.is_active ? "فعال" : "غیرفعال"}
                  />
                  <Badge
                    value={channel.reply_mode === "auto" ? "running" : "queued"}
                    label={channel.reply_mode === "auto" ? "پاسخ خودکار" : "بدون پاسخ"}
                  />
                </div>
              }
            />
            <div className="card-body space-y-3">
              <div className="rounded-lg bg-ink-50 p-3">
                <p className="text-xs text-ink-500">آدرس وبهوک (در پنل پیام‌رسان ثبت کنید)</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <code className="ltr flex-1 break-all text-xs">{url}</code>
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs"
                    onClick={() => void copy(url)}
                  >
                    {copied === url ? "کپی شد" : "کپی"}
                  </button>
                </div>
                <p className="mt-2 text-[11px] text-ink-400">
                  {isWhatsApp
                    ? "متا هم GET (تأیید verify token) و هم POST (امضای HMAC) را به همین مسیر می‌فرستد."
                    : "setWebhook(url, secret_token) — همان مقدار secret را هنگام ساخت کانال وارد کرده‌اید."}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
                <span>رویدادها: {channel.events_count}</span>
                {channel.last_event_at ? (
                  <span>آخرین: {new Date(channel.last_event_at).toLocaleString("fa-IR")}</span>
                ) : (
                  <span>هنوز پیامی نیامده</span>
                )}
                {channel.last_event_status ? (
                  <span className="rounded-full bg-ink-100 px-2 py-0.5">
                    وضعیت آخرین پیام: {channel.last_event_status}
                    {channel.last_reply_status ? ` · پاسخ: ${channel.last_reply_status}` : ""}
                  </span>
                ) : null}
                {channel.has_secret ? <span>· کلید ثبت‌شده</span> : null}
              </div>
              {channel.last_error ? (
                <p className="text-xs text-rose-600">آخرین خطا: {channel.last_error}</p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-primary !px-2 !py-1 text-xs"
                  onClick={() => void runTest(channel)}
                  disabled={!canEdit || busy === `test-${channel.id}`}
                  title="یک پیام ساختگی می‌فرستد و اجرا + پاسخ را همان‌جا نشان می‌دهد"
                >
                  {busy === `test-${channel.id}` ? "در حال تست…" : "تست وبهوک"}
                </button>
                {!isWhatsApp && canEdit ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs"
                    onClick={() => void registerWebhook(channel)}
                    disabled={busy === `hook-${channel.id}` || !channel.tool_id}
                    title="setWebhook را با توکن رباتِ همین کانال صدا می‌زند"
                  >
                    {busy === `hook-${channel.id}` ? "…" : "ثبت وبهوک در تلگرام"}
                  </button>
                ) : null}
                <button
                  className="btn-ghost !px-2 !py-1 text-xs"
                  onClick={() => void loadEvents(channel)}
                  disabled={busy === `ev-${channel.id}`}
                >
                  {events[channel.id] ? "بستن رویدادها" : "رویدادها"}
                </button>
                {canEdit ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs"
                    disabled={busy === channel.id}
                    onClick={() =>
                      void act(channel.id, () =>
                        clientFetch(`/channels/${channel.id}`, {
                          method: "PATCH",
                          body: JSON.stringify({ is_active: !channel.is_active }),
                        }),
                      )
                    }
                  >
                    {channel.is_active ? "غیرفعال کن" : "فعال کن"}
                  </button>
                ) : null}
                {canEdit ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
                    disabled={busy === `del-${channel.id}`}
                    onClick={() => {
                      if (!window.confirm("کانال و رویدادهایش حذف شود؟")) return;
                      void act(`del-${channel.id}`, () =>
                        clientFetch(`/channels/${channel.id}`, { method: "DELETE" }),
                      );
                    }}
                  >
                    حذف
                  </button>
                ) : null}
              </div>

              {test ? (
                <div
                  className={`rounded-lg border px-3 py-2 text-xs ${
                    test.needs_approval
                      ? "border-amber-200 bg-amber-50 text-amber-800"
                      : test.ok
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-rose-200 bg-rose-50 text-rose-800"
                  }`}
                >
                  <p className="font-medium">
                    {test.needs_approval
                      ? "اجرا در انتظار تأیید ماند (ابزاری نیاز به تأیید انسانی دارد)"
                      : `نتیجهٔ تست: ${test.status}`}
                    {test.run_status ? ` · اجرا: ${test.run_status}` : ""}
                    {test.reply_status ? ` · پاسخ: ${test.reply_status}` : ""}
                  </p>
                  {test.needs_approval ? (
                    <p className="mt-1">
                      پاسخی ارسال نشد. از صفحهٔ اجراها آن را تأیید کنید تا ادامه یابد.
                    </p>
                  ) : null}
                  {test.text ? <p className="mt-1 whitespace-pre-wrap">{test.text}</p> : null}
                  {test.run_id ? (
                    <Link href={`/runs/${test.run_id}`} className="mt-1 inline-block underline">
                      مشاهدهٔ اجرا
                    </Link>
                  ) : null}
                </div>
              ) : null}

              {hook ? (
                <div
                  className={`rounded-lg border px-3 py-2 text-xs ${
                    hook.ok
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}
                >
                  <p className="font-medium">
                    {hook.ok ? "وبهوک در تلگرام ثبت شد" : "ثبت وبهوک ناموفق بود"}
                  </p>
                  <p className="ltr mt-1 break-all">{hook.url}</p>
                  {hook.detail ? <p className="mt-1">{hook.detail}</p> : null}
                  {!hook.public_base_url ? (
                    <p className="mt-1">
                      آدرس از درخواست محلی ساخته شد؛ برای تلگرام باید دامنهٔ عمومی باشد
                      (`APP_PUBLIC_BASE_URL`).
                    </p>
                  ) : null}
                </div>
              ) : null}

              {events[channel.id] ? (
                <div className="overflow-x-auto rounded-lg border border-ink-100">
                  <table className="w-full text-xs">
                    <thead className="bg-ink-50 text-ink-500">
                      <tr>
                        <th className="px-2 py-1.5 text-right">زمان</th>
                        <th className="px-2 py-1.5 text-right">فرستنده</th>
                        <th className="px-2 py-1.5 text-right">متن</th>
                        <th className="px-2 py-1.5 text-right">وضعیت</th>
                        <th className="px-2 py-1.5 text-right">پاسخ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events[channel.id].length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-2 py-3 text-center text-ink-400">
                            رویدادی نیست
                          </td>
                        </tr>
                      ) : (
                        events[channel.id].map((event) => (
                          <tr key={event.id} className="border-t border-ink-100">
                            <td className="px-2 py-1.5 text-ink-500">
                              {event.created_at
                                ? new Date(event.created_at).toLocaleString("fa-IR")
                                : "—"}
                            </td>
                            <td className="ltr px-2 py-1.5">{event.from_id ?? "—"}</td>
                            <td className="max-w-56 truncate px-2 py-1.5">{event.text ?? "—"}</td>
                            <td className="px-2 py-1.5">
                              <Badge value={event.status} />
                            </td>
                            <td className="px-2 py-1.5 text-ink-500">
                              {event.reply_status ?? "—"}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
