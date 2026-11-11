import { Card, CardHeader, ProgressBar, Stat } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { formatJalali, formatMoney, formatNumber } from "@/lib/format";
import type { UsageSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function UsagePage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const params = await searchParams;
  const days = Number(params.days ?? 30);
  const safeDays = Number.isFinite(days) && days > 0 && days <= 365 ? days : 30;
  const summary = await serverFetch<UsageSummary>(`/usage/summary?days=${safeDays}`);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">مصرف و هزینه</h1>
          <p className="muted mt-1">
            {formatJalali(summary.range_from)} تا {formatJalali(summary.range_to)} · نرخ ارز{" "}
            {formatNumber(summary.fx_rate)} ریال
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map((value) => (
            <a
              key={value}
              href={`/usage?days=${value}`}
              className={`btn-ghost ${safeDays === value ? "!border-brand-400 !text-brand-700" : ""}`}
            >
              {formatNumber(value)} روز
            </a>
          ))}
          <a className="btn-primary" href={`/api/usage/export.xlsx?days=${safeDays}`}>
            خروجی اکسل
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="اجرا" value={formatNumber(summary.totals.runs)} />
        <Stat
          label="توکن ورودی"
          value={formatNumber(summary.totals.tokens_in)}
          hint={`${formatNumber(summary.totals.tokens_out)} خروجی`}
        />
        <Stat
          label="هزینه (تومان)"
          value={formatMoney(summary.totals.cost_irr, { withUnit: false })}
          hint={`${summary.totals.cost_usd} دلار`}
        />
        <Stat
          label="در انتظار تأیید"
          value={formatNumber(summary.pending_approvals)}
          tone={summary.pending_approvals > 0 ? "warning" : "default"}
        />
      </div>

      {summary.fx_rate === 0 ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-800">
          نرخ ارز تنظیم نشده است؛ هزینه‌ی ریالی صفر ثبت می‌شود. آن را در «تنظیمات» وارد کنید.
        </div>
      ) : null}

      {summary.budget.org_monthly_irr ? (
        <Card>
          <div className="card-body space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-ink-800">بودجه‌ی ماه جاری</span>
              <span className="tabular text-ink-600">
                {formatMoney(summary.budget.org_spent_irr)} از{" "}
                {formatMoney(summary.budget.org_monthly_irr)}
              </span>
            </div>
            <ProgressBar
              value={summary.budget.org_spent_irr}
              max={summary.budget.org_monthly_irr}
            />
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {[
          { title: "بر اساس ایجنت", rows: summary.by_agent },
          { title: "بر اساس مدل", rows: summary.by_model },
        ].map((section) => (
          <Card key={section.title}>
            <CardHeader title={section.title} />
            <div className="card-body">
              {section.rows.length === 0 ? (
                <p className="muted">داده‌ای نیست.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-right text-xs text-ink-500">
                      <th className="pb-2 font-medium">عنوان</th>
                      <th className="pb-2 font-medium">اجرا</th>
                      <th className="pb-2 font-medium">توکن</th>
                      <th className="pb-2 font-medium">هزینه</th>
                    </tr>
                  </thead>
                  <tbody>
                    {section.rows.map((row) => (
                      <tr key={row.key} className="border-t border-ink-100">
                        <td className="py-2">{row.label}</td>
                        <td className="py-2 tabular">{formatNumber(row.runs)}</td>
                        <td className="py-2 tabular">
                          {formatNumber(row.tokens_in + row.tokens_out)}
                        </td>
                        <td className="py-2 tabular">{formatMoney(row.cost_irr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
