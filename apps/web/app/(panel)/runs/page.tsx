import Link from "next/link";

import { RunActions } from "@/components/run-actions";
import { Badge, Card, EmptyState } from "@/components/ui";
import { buildQuery } from "@/lib/api";
import { serverFetch } from "@/lib/api-server";
import { statusLabels, triggerLabels } from "@/lib/copy";
import { formatDateTime, formatMoney, formatNumber } from "@/lib/format";
import type { Agent, Run } from "@/lib/types";

export const dynamic = "force-dynamic";

const FILTERS = ["", "waiting_approval", "running", "completed", "failed", "cancelled"];

export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; agent_id?: string }>;
}) {
  const params = await searchParams;
  const status = params.status ?? "";
  const query = buildQuery({ status: status || undefined, agent_id: params.agent_id, limit: 100 });

  const [runs, agents] = await Promise.all([
    serverFetch<Run[]>(`/runs${query}`),
    serverFetch<Agent[]>("/agents").catch(() => [] as Agent[]),
  ]);

  const agentNames: Record<string, string> = {};
  for (const agent of agents) agentNames[agent.id] = agent.name;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">اجراها</h1>
          <p className="muted mt-1">
            هر اجرا با هزینه و رخدادهایش ذخیره می‌شود؛ درخواست‌های پرخطر تا تأیید شما متوقف می‌مانند.
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((value) => (
            <Link
              key={value || "all"}
              href={value ? `/runs?status=${value}` : "/runs"}
              className={`btn-ghost !px-3 !py-1.5 text-xs ${
                status === value ? "!border-brand-400 !text-brand-700" : ""
              }`}
            >
              {value ? statusLabels[value] : "همه"}
            </Link>
          ))}
        </div>
      </div>

      {runs.length === 0 ? (
        <Card>
          <EmptyState
            title="اجرایی ثبت نشده"
            description="از آزمایشگاه یک ایجنت را اجرا کنید تا اینجا ثبت شود."
            action={
              <Link className="btn-primary" href="/playground">
                رفتن به آزمایشگاه
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="table-wrapper">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">ایجنت</th>
                <th className="th">وضعیت</th>
                <th className="th">تریگر</th>
                <th className="th">گام</th>
                <th className="th">توکن</th>
                <th className="th">هزینه</th>
                <th className="th">شروع</th>
                <th className="th">خطا</th>
                <th className="th">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-ink-50/60">
                  <td className="td">
                    <Link href={`/runs/${run.id}`} className="font-medium text-brand-700 hover:underline">
                      {run.agent_id ? agentNames[run.agent_id] ?? "—" : "—"}
                    </Link>
                    <div className="ltr text-[11px] text-ink-400">{run.id.slice(0, 8)}</div>
                  </td>
                  <td className="td">
                    <Badge value={run.status} />
                  </td>
                  <td className="td text-xs text-ink-600">
                    {triggerLabels[run.trigger] ?? run.trigger}
                  </td>
                  <td className="td tabular">{formatNumber(run.steps_taken)}</td>
                  <td className="td tabular">
                    {formatNumber(run.tokens_in)}+{formatNumber(run.tokens_out)}
                  </td>
                  <td className="td tabular">{formatMoney(run.cost_irr)}</td>
                  <td className="td text-xs">{formatDateTime(run.created_at)}</td>
                  <td className="td text-xs text-rose-600">{run.error_code ?? "—"}</td>
                  <td className="td">
                    <RunActions run={run} />
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
