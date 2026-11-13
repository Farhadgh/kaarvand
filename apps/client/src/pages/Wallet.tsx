import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { openExternal } from "../lib/desktop";
import { faError } from "../lib/errors-fa";
import { faDigits, formatToman } from "../lib/money";

/** Top-up amounts in Toman; the API converts to Rial for the gateway. */
const PRESETS = [50_000, 100_000, 200_000, 500_000];

const STATUS_LABELS: Record<string, string> = {
  paid: "پرداخت‌شده",
  pending: "در انتظار پرداخت",
  canceled: "لغو‌شده",
  failed: "ناموفق",
};

const STATUS_TONES: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-700",
  pending: "bg-amber-50 text-amber-700",
  canceled: "bg-slate-100 text-slate-600",
  failed: "bg-rose-50 text-rose-700",
};

export default function Wallet() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState<number>(100_000);
  const [error, setError] = useState<string | null>(null);

  const wallet = useQuery({ queryKey: ["wallet"], queryFn: api.wallet });
  const payments = useQuery({ queryKey: ["payments"], queryFn: api.payments });

  const returned = params.get("status");

  // A deep link from the gateway (`kaarvand://wallet?status=paid`) lands here;
  // refresh the balance as soon as we see it.
  useEffect(() => {
    if (!returned) return;
    void queryClient.invalidateQueries({ queryKey: ["wallet"] });
    void queryClient.invalidateQueries({ queryKey: ["payments"] });
  }, [returned, queryClient]);

  const pay = useMutation({
    mutationFn: (toman: number) => api.topup(toman),
    onSuccess: async (result) => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["payments"] });
      await openExternal(result.redirect_url);
    },
    onError: (err) => setError(faError((err as ApiError).code)),
  });

  const minimum = wallet.data?.min_topup_toman ?? 10_000;
  const topupEnabled = wallet.data?.topup_enabled ?? false;
  const tooSmall = amount < minimum;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">کیف پول</h1>
      </header>

      {returned === "paid" ? (
        <p className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          پرداخت با موفقیت انجام شد و کیف پول شارژ شد.
        </p>
      ) : null}
      {returned === "canceled" || returned === "failed" ? (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
          پرداخت انجام نشد. اگر مبلغی کسر شده باشد تا ۷۲ ساعت به حساب شما برمی‌گردد.
        </p>
      ) : null}

      <section className="rounded-2xl bg-brand-500 p-5 text-white shadow-sm">
        <p className="text-xs opacity-80">موجودی فعلی</p>
        <p className="mt-2 text-2xl font-bold">
          {wallet.isLoading
            ? "…"
            : wallet.isError
              ? "خطا در دریافت موجودی"
              : formatToman(wallet.data?.balance_irr ?? 0)}
        </p>
      </section>

      <section className="card space-y-3">
        <p className="text-sm font-semibold">مبلغ شارژ (تومان)</p>

        <div className="grid grid-cols-2 gap-2">
          {PRESETS.map((value) => (
            <button
              key={value}
              className={`rounded-xl border px-3 py-2 text-sm ${
                amount === value
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
              onClick={() => setAmount(value)}
            >
              {faDigits(value.toLocaleString("en-US"))}
            </button>
          ))}
        </div>

        <input
          className="input text-center"
          inputMode="numeric"
          value={amount}
          onChange={(event) => {
            const digits = event.target.value.replace(/[^0-9۰-۹]/g, "");
            const latin = digits.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
            setAmount(Number(latin || 0));
          }}
        />

        <p className="text-xs text-slate-500">
          حداقل شارژ {faDigits(minimum.toLocaleString("en-US"))} تومان است.
        </p>

        {topupEnabled ? (
          <button
            className="btn-primary w-full"
            disabled={pay.isPending || tooSmall}
            onClick={() => pay.mutate(amount)}
          >
            {pay.isPending ? "در حال انتقال به درگاه…" : "پرداخت با زرین‌پال"}
          </button>
        ) : (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            درگاه پرداخت هنوز فعال نشده است؛ به‌زودی شارژ آنلاین باز می‌شود.
          </p>
        )}

        {error ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>
        ) : null}
      </section>

      <section className="space-y-2">
        <p className="text-sm font-semibold">پرداخت‌های من</p>
        {payments.isLoading ? (
          <p className="text-xs text-slate-400">در حال بارگذاری…</p>
        ) : (payments.data ?? []).length === 0 ? (
          <p className="text-xs text-slate-400">هنوز پرداختی ثبت نشده است.</p>
        ) : (
          (payments.data ?? []).map((payment) => (
            <div key={payment.id} className="card flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{formatToman(payment.amount_irr)}</p>
                <p className="text-xs text-slate-400">
                  {payment.reference
                    ? `شماره پیگیری ${faDigits(payment.reference)}`
                    : (payment.description_fa ?? "شارژ کیف پول")}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-1 text-xs ${
                  STATUS_TONES[payment.status] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {STATUS_LABELS[payment.status] ?? payment.status}
              </span>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
