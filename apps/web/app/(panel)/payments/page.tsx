import { PaymentRowActions } from "@/components/payment-row-actions";
import { Badge, Card, EmptyState, Stat } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { formatDateTime, formatMoney, formatNumber, toFaDigits } from "@/lib/format";
import type { Payment, PaymentSummary, User } from "@/lib/types";

export const dynamic = "force-dynamic";

const STATUSES = ["paid", "pending", "failed", "canceled"] as const;

export default async function PaymentsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; days?: string }>;
}) {
  const me = await serverFetch<User>("/auth/me");
  if (me.role !== "admin") {
    return (
      <Card>
        <EmptyState
          title="دسترسی ندارید"
          description="گزارش پرداخت‌ها و تسویه فقط برای مدیر سامانه است."
        />
      </Card>
    );
  }

  const params = await searchParams;
  const status = STATUSES.includes(params.status as (typeof STATUSES)[number])
    ? (params.status as string)
    : "";
  const days = [7, 30, 90].includes(Number(params.days)) ? Number(params.days) : 30;

  const query = new URLSearchParams({ limit: "100" });
  if (status) query.set("status", status);

  const [summary, rows] = await Promise.all([
    serverFetch<PaymentSummary>(`/payments/summary?days=${days}`),
    serverFetch<Payment[]>(`/payments?${query.toString()}`),
  ]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">پرداخت‌ها</h1>
          <p className="muted mt-1">
            شارژ کیف پول کاربران از درگاه؛ فقط پرداخت‌های «پرداخت‌شده» موجودی می‌سازند.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((value) => (
            <a
              key={value}
              href={`/payments?days=${value}${status ? `&status=${status}` : ""}`}
              className={`btn-ghost ${days === value ? "!border-brand-400 !text-brand-700" : ""}`}
            >
              {formatNumber(value)} روز
            </a>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="درآمد تسویه‌شده"
          value={formatMoney(summary.paid_irr, { withUnit: false })}
          hint={`${formatNumber(summary.paid_count)} پرداخت موفق (تومان)`}
          tone="success"
        />
        <Stat
          label="امروز"
          value={formatMoney(summary.today_paid_irr, { withUnit: false })}
          hint="تومان"
        />
        <Stat
          label="در انتظار پرداخت"
          value={formatNumber(summary.pending_count)}
          tone={summary.pending_count > 0 ? "warning" : "default"}
        />
        <Stat
          label="ناموفق / لغو‌شده"
          value={`${formatNumber(summary.failed_count)} / ${formatNumber(summary.canceled_count)}`}
          tone={summary.failed_count > 0 ? "danger" : "default"}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <a
          href={`/payments?days=${days}`}
          className={`btn-ghost ${status === "" ? "!border-brand-400 !text-brand-700" : ""}`}
        >
          همه
        </a>
        {STATUSES.map((value) => (
          <a
            key={value}
            href={`/payments?days=${days}&status=${value}`}
            className={`btn-ghost ${status === value ? "!border-brand-400 !text-brand-700" : ""}`}
          >
            {value === "paid"
              ? "پرداخت‌شده"
              : value === "pending"
                ? "در انتظار"
                : value === "failed"
                  ? "ناموفق"
                  : "لغو‌شده"}
          </a>
        ))}
      </div>

      {rows.length === 0 ? (
        <Card>
          <EmptyState title="پرداختی ثبت نشده" description="با اولین شارژ کیف پول، این جدول پر می‌شود." />
        </Card>
      ) : (
        <div className="table-wrapper">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">تاریخ</th>
                <th className="th">کاربر</th>
                <th className="th">موبایل</th>
                <th className="th">مبلغ (تومان)</th>
                <th className="th">درگاه</th>
                <th className="th">وضعیت</th>
                <th className="th">شماره پیگیری</th>
                <th className="th">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-ink-50/60">
                  <td className="td text-xs">{formatDateTime(row.created_at)}</td>
                  <td className="td font-medium text-ink-900">{row.user_name ?? "—"}</td>
                  <td className="td ltr text-xs">{row.user_phone ?? "—"}</td>
                  <td className="td tabular">{formatMoney(row.amount_irr, { withUnit: false })}</td>
                  <td className="td text-xs ltr">{row.gateway}</td>
                  <td className="td">
                    <Badge value={row.status} />
                  </td>
                  <td className="td ltr text-xs">
                    {row.reference ? toFaDigits(row.reference) : "—"}
                  </td>
                  <td className="td">
                    {row.status === "pending" ? (
                      <PaymentRowActions paymentId={row.id} />
                    ) : (
                      <span className="text-xs text-ink-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
