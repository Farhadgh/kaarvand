import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { clearSession, loadSession } from "../lib/auth";
import { faDigits, formatToman } from "../lib/money";

/** First screen after login: wallet balance plus the roadmap of the app. */
export default function Home() {
  const navigate = useNavigate();
  const session = loadSession();
  const wallet = useQuery({ queryKey: ["wallet"], queryFn: api.wallet });

  function logout() {
    const refresh = loadSession()?.refreshToken;
    if (refresh) void api.logout(refresh).catch(() => undefined);
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-500">خوش آمدید</p>
          <h1 className="text-lg font-bold">{session?.user.full_name ?? "کاربر کاروند"}</h1>
          {session?.user.phone ? (
            <p className="text-xs text-slate-400">{faDigits(session.user.phone)}</p>
          ) : null}
        </div>
        <button className="btn-ghost text-xs" onClick={logout}>
          خروج
        </button>
      </header>

      <section className="rounded-2xl bg-brand-500 p-5 text-white shadow-sm">
        <p className="text-xs opacity-80">موجودی کیف پول</p>
        <p className="mt-2 text-2xl font-bold">
          {wallet.isLoading
            ? "…"
            : wallet.isError
              ? "خطا در دریافت موجودی"
              : formatToman(wallet.data?.balance_irr ?? 0)}
        </p>
        <button
          className="mt-4 rounded-xl bg-white/15 px-4 py-2 text-sm hover:bg-white/25"
          onClick={() => navigate("/wallet")}
        >
          شارژ کیف پول
        </button>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <button className="card text-right" onClick={() => navigate("/models")}>
          <p className="text-sm font-semibold">مدل‌ها</p>
          <p className="mt-1 text-xs text-slate-500">انتخاب مدل فارسی با قیمت تومانی</p>
        </button>
        <button className="card text-right" onClick={() => navigate("/agents")}>
          <p className="text-sm font-semibold">ایجنت‌ها</p>
          <p className="mt-1 text-xs text-slate-500">ساخت و مدیریت دستیارهای هوشمند</p>
        </button>
        <button className="card text-right" onClick={() => navigate("/connections")}>
          <p className="text-sm font-semibold">اتصال‌ها</p>
          <p className="mt-1 text-xs text-slate-500">پیام‌رسان، دستگاه من، برنامهٔ من</p>
        </button>
        <button className="card text-right" onClick={() => navigate("/runs")}>
          <p className="text-sm font-semibold">گفتگوها</p>
          <p className="mt-1 text-xs text-slate-500">تاریخچهٔ اجراها و هزینه‌ها</p>
        </button>
      </section>

      <p className="pt-2 text-center text-xs text-slate-400">
        نسخهٔ {faDigits("0.1.0")} — این بخش‌ها در گام‌های بعدی فعال می‌شوند.
      </p>
    </div>
  );
}
