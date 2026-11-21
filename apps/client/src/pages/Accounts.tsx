import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError, type LinkProvider, type LinkedAccount } from "../lib/api";
import { desktop } from "../lib/desktop";
import { loadDevice } from "../lib/device";
import { faError } from "../lib/errors-fa";
import { faDigits } from "../lib/money";

const STATUS_FA: Record<LinkedAccount["status"], string> = {
  pending: "منتظر ورود",
  active: "فعال",
  paused: "متوقف",
  error: "خطا",
  revoked: "قطع‌شده",
};

const STATUS_STYLE: Record<LinkedAccount["status"], string> = {
  pending: "bg-amber-50 text-amber-700",
  active: "bg-emerald-50 text-emerald-700",
  paused: "bg-slate-100 text-slate-600",
  error: "bg-rose-50 text-rose-700",
  revoked: "bg-slate-100 text-slate-500",
};

type Notice = { kind: "ok" | "info" | "error"; text: string };

/**
 * «حساب‌های من»: a customer's own social accounts.
 *
 * The password never reaches us: the desktop app opens a window for the site,
 * the customer logs in once, the session stays in that device's profile, and a
 * probe turns the login into agent tools.
 */
export default function Accounts() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [shot, setShot] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const providers = useQuery({ queryKey: ["link-providers"], queryFn: api.linkProviders });
  const links = useQuery({ queryKey: ["links"], queryFn: api.links });
  const device = useQuery({ queryKey: ["device"], queryFn: loadDevice });
  const hasBridge = Boolean(desktop()?.bridge);

  const linked = new Map((links.data ?? []).map((link) => [link.provider, link]));

  function fail(err: unknown) {
    const code = (err as ApiError).code;
    setNotice({ kind: "error", text: faError(code) });
    if (code === "link.already_exists") {
      void queryClient.invalidateQueries({ queryKey: ["links"] });
    }
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["links"] });
  }

  const connect = useMutation({
    mutationFn: (provider: string) => api.createLink(provider),
    onSuccess: async (link) => {
      setShot(null);
      setNotice(
        link.login_opened
          ? {
              kind: "info",
              text: "پنجرهٔ ورود باز شد. وارد حساب خودتان شوید، بعد «بررسی اتصال» را بزنید.",
            }
          : {
              kind: "info",
              text: "حساب ساخته شد. برای باز شدن پنجرهٔ ورود، اپ کاروند را روی لپ‌تاپ خود باز کنید.",
            },
      );
      await refresh();
    },
    onError: fail,
  });

  const open = useMutation({
    mutationFn: (id: string) => api.openLink(id),
    onSuccess: async () => {
      setNotice({ kind: "info", text: "پنجرهٔ ورود دوباره باز شد." });
      await refresh();
    },
    onError: fail,
  });

  const probe = useMutation({
    mutationFn: (id: string) => api.probeLink(id),
    onSuccess: async (result) => {
      setShot(result.screenshot ?? null);
      if (result.logged_in) {
        setNotice({
          kind: "ok",
          text: `اتصال برقرار شد${
            result.display_name ? ` — ${result.display_name}` : ""
          }. ${faDigits(result.tools.length)} ابزار برای ایجنت‌ها ساخته شد.`,
        });
      } else {
        setNotice({
          kind: "info",
          text: result.hint_fa ?? "هنوز وارد نشده‌اید؛ پنجرهٔ ورود را باز کنید.",
        });
      }
      await refresh();
    },
    onError: fail,
  });

  const stop = useMutation({
    mutationFn: (id: string) => api.stopLink(id),
    onSuccess: async () => {
      setNotice({ kind: "info", text: "دسترسی متوقف شد؛ ایجنت‌ها دیگر کاری انجام نمی‌دهند." });
      await refresh();
    },
    onError: fail,
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteLink(id),
    onSuccess: async () => {
      setShot(null);
      setNotice({ kind: "info", text: "حساب قطع شد و نشستِ ذخیره‌شده روی دستگاه پاک شد." });
      await refresh();
    },
    onError: fail,
  });

  async function run(key: string, work: () => Promise<unknown>) {
    setBusy(key);
    try {
      await work();
    } finally {
      setBusy(null);
    }
  }

  const card = (provider: LinkProvider) => {
    const link = linked.get(provider.slug);
    const key = provider.slug;
    const working = busy === key || connect.isPending;

    return (
      <article key={provider.slug} className="card space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">{provider.title_fa}</p>
            <p className="text-xs text-slate-400" dir="ltr">
              {provider.site_url.replace("https://", "").replace(/\/$/, "")}
            </p>
          </div>
          {link ? (
            <span className={`rounded-full px-2 py-1 text-[11px] ${STATUS_STYLE[link.status]}`}>
              {STATUS_FA[link.status]}
            </span>
          ) : provider.available ? (
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500">
              وصل نشده
            </span>
          ) : (
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500">
              به‌زودی
            </span>
          )}
        </div>

        {link ? (
          <p className="text-xs text-slate-600">
            {link.display_name ?? "بدون نام"} · {faDigits(link.tool_slugs.length)} ابزار · سقف{" "}
            {faDigits(link.rate_limit_per_hour)} بار در ساعت
            {link.device_id ? (link.device_online ? " · دستگاه آنلاین" : " · دستگاه آفلاین") : ""}
          </p>
        ) : (
          <p className="text-xs text-slate-500">{provider.login_hint_fa}</p>
        )}

        {provider.tools.length > 0 ? (
          <ul className="space-y-1 text-[11px] text-slate-500">
            {provider.tools.map((tool) => (
              <li key={tool.name}>• {tool.title_fa}</li>
            ))}
          </ul>
        ) : null}

        {provider.notes_fa ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
            {provider.notes_fa}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {link ? (
            <>
              <button
                className="btn-primary px-3 py-1.5 text-xs"
                disabled={busy === key || probe.isPending}
                onClick={() => void run(key, () => probe.mutateAsync(link.id))}
              >
                بررسی اتصال
              </button>
              <button
                className="btn-ghost px-3 py-1.5 text-xs"
                disabled={busy === key || open.isPending}
                onClick={() => void run(key, () => open.mutateAsync(link.id))}
              >
                پنجرهٔ ورود
              </button>
              <button
                className="btn-ghost px-3 py-1.5 text-xs"
                disabled={busy === key || stop.isPending || link.status === "paused"}
                onClick={() => void run(key, () => stop.mutateAsync(link.id))}
              >
                توقف
              </button>
              <button
                className="btn-ghost px-3 py-1.5 text-xs text-rose-700"
                disabled={busy === key || remove.isPending}
                onClick={() => {
                  if (
                    window.confirm(
                      `«${provider.title_fa}» قطع شود؟ نشست ذخیره‌شده هم پاک می‌شود.`,
                    )
                  )
                    void run(key, () => remove.mutateAsync(link.id));
                }}
              >
                قطع و پاک‌کردن
              </button>
            </>
          ) : (
            <button
              className="btn-primary px-3 py-1.5 text-xs"
              disabled={!provider.available || working}
              onClick={() => void run(key, () => connect.mutateAsync(provider.slug))}
            >
              {provider.available ? "اتصال" : "به‌زودی"}
            </button>
          )}
        </div>
      </article>
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">حساب‌های من</h1>
      </header>

      <p className="rounded-xl bg-slate-100 px-3 py-2 text-xs text-slate-600">
        یک‌بار وارد حساب خودتان می‌شوید؛ نشست روی همین دستگاه می‌ماند و ایجنت‌ها به‌جای شما کار
        می‌کنند. رمز شما هرگز به سرور نمی‌رسد و هر کار حساس یک تأیید انسانی دارد.
      </p>

      <p
        className={`rounded-xl px-3 py-2 text-xs ${
          !hasBridge
            ? "bg-amber-50 text-amber-800"
            : device.data
              ? "bg-emerald-50 text-emerald-700"
              : "bg-slate-100 text-slate-600"
        }`}
      >
        {!hasBridge
          ? "برای اتصال حساب‌ها به اپ دسکتاپ کاروند نیاز است؛ در مرورگر، نشست سایت را نمی‌توانیم نگه داریم."
          : device.data
            ? `این دستگاه متصل است (${device.data.deviceId.slice(0, 8)}).`
            : "این دستگاه در حال آماده‌سازی است…"}
      </p>

      {notice ? (
        <p
          className={`rounded-xl px-3 py-2 text-xs ${
            notice.kind === "ok"
              ? "bg-emerald-50 text-emerald-700"
              : notice.kind === "error"
                ? "bg-rose-50 text-rose-700"
                : "bg-sky-50 text-sky-800"
          }`}
        >
          {notice.text}
        </p>
      ) : null}

      {shot ? (
        <details className="card">
          <summary className="cursor-pointer text-xs text-slate-600">
            تصویری که دستگاه دیده است
          </summary>
          <img
            className="mt-2 w-full rounded-xl border border-slate-200"
            src={`data:image/png;base64,${shot}`}
            alt="نمای صفحه"
          />
        </details>
      ) : null}

      {providers.isLoading || links.isLoading ? (
        <p className="text-xs text-slate-400">در حال بارگذاری…</p>
      ) : providers.isError ? (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
          فهرست حساب‌ها دریافت نشد. اتصال اینترنت خود را بررسی کنید.
        </p>
      ) : (
        <section className="space-y-3">{(providers.data ?? []).map(card)}</section>
      )}
    </div>
  );
}

