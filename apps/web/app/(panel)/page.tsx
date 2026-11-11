import Link from "next/link";

import { DailyCostCard, TopAgentsCard } from "@/components/dashboard-charts";
import { Card, EmptyState, ProgressBar, Stat } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { formatJalali, formatMoney, formatNumber } from "@/lib/format";
import type { UsageSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let summary: UsageSummary | null = null;
  try {
    summary = await serverFetch<UsageSummary>("/usage/summary?days=30");
  } catch {
    summary = null;
  }

  if (!summary) {
    return (
      <Card>
        <EmptyState
          title="داشبورد در دسترس نیست"
          description="ارتباط با سرور برقرار نشد. وضعیت سرویس را بررسی کنید."
          action={
            <Link className="btn-primary" href="/settings">
              بررسی تنظیمات
            </Link>
          }
        />
      </Card>
    );
  }

  const budget = summary.budget.org_monthly_irr;
  const spent = summary.budget.org_spent_irr;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">داشبورد</h1>
          <p className="muted mt-1">
            بازه‌ی {formatJalali(summary.range_from)} تا {formatJalali(summary.range_to)} — نرخ ارز{" "}
            {formatNumber(summary.fx_rate)} ریال
          </p>
        </div>
        <Link href="/playground" className="btn-primary">
          اجرای سریع ایجنت
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="اجراهای این بازه"
          value={formatNumber(summary.totals.runs)}
          hint={`${formatNumber(summary.runs.completed)} تکمیل‌شده · ${formatNumber(summary.runs.failed)} ناموفق`}
        />
        <Stat
          label="هزینه (تومان)"
          value={formatMoney(summary.totals.cost_irr, { withUnit: false })}
          hint={`${formatNumber(summary.totals.tokens_in)} توکن ورودی · ${formatNumber(summary.totals.tokens_out)} خروجی`}
        />
        <Stat
          label="ایجنت‌ها"
          value={`${formatNumber(summary.agents_active)} / ${formatNumber(summary.agents_total)}`}
          hint="فعال / کل"
        />
        <Stat
          label="دستگاه‌ها"
          value={`${formatNumber(summary.devices_online)} / ${formatNumber(summary.devices_total)}`}
          hint="آنلاین / کل"
          tone={summary.devices_online === 0 ? "warning" : "success"}
        />
      </div>

      {summary.fx_rate === 0 ? (
        <div className="rounded-xl2 border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
          نرخ ارز تنظیم نشده است، بنابراین هزینه‌ی ریالی صفر ثبت می‌شود. مقدار «هر دلار» را در{" "}
          <Link href="/settings" className="font-medium underline">
            تنظیمات
          </Link>{" "}
          وارد کنید (یا متغیر <code className="rounded bg-rose-100 px-1">APP_FX_USD_IRR</code> را در سرور بگذارید).
        </div>
      ) : null}

      {summary.pending_approvals > 0 ? (
        <div className="rounded-xl2 border border-amber-200 bg-amber-50 px-5 py-4">
          <p className="font-medium text-amber-800">
            {formatNumber(summary.pending_approvals)} اجرا در انتظار تأیید شماست.
          </p>
          <Link
            href="/runs?status=waiting_approval"
            className="mt-2 inline-block text-sm font-medium text-amber-700 underline"
          >
            مشاهده و تأیید
          </Link>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DailyCostCard summary={summary} />
        <TopAgentsCard summary={summary} />
      </div>

      {budget ? (
        <Card>
          <div className="card-body space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-ink-800">بودجه‌ی ماهانه‌ی سازمان</span>
              <span className="tabular text-ink-500">
                {formatMoney(spent)} از {formatMoney(budget)}
              </span>
            </div>
            <ProgressBar value={spent} max={budget} />
          </div>
        </Card>
      ) : null}
    </div>
  );
}
