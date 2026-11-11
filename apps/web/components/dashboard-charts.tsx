import { Card, CardHeader, ProgressBar } from "@/components/ui";
import { formatMoney, formatNumber } from "@/lib/format";
import type { UsageSummary } from "@/lib/types";

export function DailyCostCard({ summary }: { summary: UsageSummary }) {
  const max = Math.max(...summary.by_day.map((row) => row.cost_irr), 1);
  return (
    <Card>
      <CardHeader title="هزینه‌ی روزهای اخیر" subtitle="به تومان" />
      <div className="card-body">
        {summary.by_day.length === 0 ? (
          <p className="muted">هنوز مصرفی ثبت نشده است.</p>
        ) : (
          <ul className="space-y-2">
            {summary.by_day.slice(-10).map((day) => (
              <li key={day.key} className="flex items-center gap-3">
                <span className="w-24 shrink-0 text-xs text-ink-500">{day.label}</span>
                <span className="flex-1">
                  <ProgressBar value={day.cost_irr} max={max} />
                </span>
                <span className="w-24 shrink-0 text-left text-xs tabular text-ink-700">
                  {formatMoney(day.cost_irr, { withUnit: false })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

export function TopAgentsCard({ summary }: { summary: UsageSummary }) {
  return (
    <Card>
      <CardHeader title="پرمصرف‌ترین ایجنت‌ها" subtitle="۳۰ روز اخیر" />
      <div className="card-body">
        {summary.by_agent.length === 0 ? (
          <p className="muted">هنوز ایجنتی اجرا نشده است.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-right text-xs text-ink-500">
                <th className="pb-2 font-medium">ایجنت</th>
                <th className="pb-2 font-medium">اجرا</th>
                <th className="pb-2 font-medium">هزینه</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_agent.slice(0, 6).map((row) => (
                <tr key={row.key} className="border-t border-ink-100">
                  <td className="py-2">{row.label}</td>
                  <td className="py-2 tabular">{formatNumber(row.runs)}</td>
                  <td className="py-2 tabular">{formatMoney(row.cost_irr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}
