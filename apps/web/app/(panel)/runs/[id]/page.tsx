import Link from "next/link";
import { notFound } from "next/navigation";

import { RunActions } from "@/components/run-actions";
import { Badge, Card, CardHeader, KeyValue } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { ApiError } from "@/lib/api-errors";
import { formatDateTime, formatMoney, formatNumber } from "@/lib/format";
import type { Run, ToolInvocation } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let run: Run;
  try {
    run = await serverFetch<Run>(`/runs/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const invocations = await serverFetch<ToolInvocation[]>(`/runs/${id}/invocations`).catch(
    () => [] as ToolInvocation[],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/runs" className="text-sm text-brand-700 hover:underline">
            ← همه‌ی اجراها
          </Link>
          <h1 className="page-title mt-1 flex items-center gap-2">
            اجرای <span className="ltr font-mono text-sm">{run.id.slice(0, 8)}</span>
            <Badge value={run.status} />
          </h1>
          <p className="muted">{formatDateTime(run.created_at)}</p>
        </div>
        <RunActions run={run} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="خلاصه" />
          <div className="card-body">
            <KeyValue label="گام‌ها">{formatNumber(run.steps_taken)}</KeyValue>
            <KeyValue label="توکن ورودی">{formatNumber(run.tokens_in)}</KeyValue>
            <KeyValue label="توکن خروجی">{formatNumber(run.tokens_out)}</KeyValue>
            <KeyValue label="هزینه">{formatMoney(run.cost_irr)}</KeyValue>
            <KeyValue label="دلار">{run.cost_usd}</KeyValue>
            <KeyValue label="نرخ ارز">{run.fx_rate ?? "—"}</KeyValue>
            <KeyValue label="تریگر">{run.trigger}</KeyValue>
            <KeyValue label="پایان">{formatDateTime(run.finished_at)}</KeyValue>
          </div>
        </Card>

        {run.error_code ? (
          <Card className="lg:col-span-2">
            <CardHeader title="خطا" />
            <div className="card-body text-sm text-rose-700">
              <p className="font-mono text-xs">{run.error_code}</p>
              <p className="mt-1">{run.error_message ?? "—"}</p>
            </div>
          </Card>
        ) : (
          <Card className="lg:col-span-2">
            <CardHeader title="وضعیت" />
            <div className="card-body text-sm text-ink-600">
              اجرا بدون خطا ذخیره شده است. برای دیدن رخدادها از آزمایشگاه دوباره اجرا کنید.
            </div>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader
          title="فراخوانی ابزارها"
          subtitle="هر فراخوانی با آرگومان و نتیجه در دفتر حسابرسی ثبت می‌شود"
        />
        <div className="card-body">
          {invocations.length === 0 ? (
            <p className="muted">این اجرا ابزاری فراخوانی نکرده است.</p>
          ) : (
            <ul className="space-y-3">
              {invocations.map((invocation) => (
                <li key={invocation.id} className="rounded-lg border border-ink-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-ink-900">{invocation.tool_slug}</span>
                    <Badge value={invocation.status} />
                    <Badge value={invocation.risk_level} />
                    <span className="text-xs text-ink-400">
                      {invocation.latency_ms ? `${invocation.latency_ms}ms` : "—"}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                    <pre className="ltr max-h-40 overflow-auto rounded bg-ink-50 p-2 text-xs">
                      {JSON.stringify(invocation.args, null, 2)}
                    </pre>
                    <pre className="ltr max-h-40 overflow-auto rounded bg-ink-50 p-2 text-xs">
                      {JSON.stringify(invocation.result, null, 2)}
                    </pre>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
