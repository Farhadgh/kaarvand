import Link from "next/link";

import { AgentCreateForm } from "@/components/agent-create-form";
import { Badge, Card, EmptyState } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { formatMoney, formatNumber } from "@/lib/format";
import type { Agent, Model, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const [agents, models, me] = await Promise.all([
    serverFetch<Agent[]>("/agents"),
    serverFetch<Model[]>("/models?capability=tools&limit=200").catch(() => [] as Model[]),
    serverFetch<User>("/auth/me"),
  ]);
  const canEdit = me.role === "owner" || me.role === "admin";
  const modelOptions = models.map((model) => ({
    id: model.id,
    label: model.display_name_fa ?? model.external_id,
  }));

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">ایجنت‌ها</h1>
        <p className="muted mt-1">
          هر ایجنت یک «کارمند» است: پرامپت، مدل، ابزار و وظایف جداگانه دارد.
        </p>
      </div>

      <AgentCreateForm models={modelOptions} canEdit={canEdit} />

      {agents.length === 0 ? (
        <Card>
          <EmptyState
            title="هنوز ایجنتی نساخته‌اید"
            description="از فرم بالا یک ایجنت بسازید؛ الگوی حسابدار یا فروشنده آماده است."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <div className="card-body space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <Link href={`/agents/${agent.id}`} className="font-bold text-ink-900 hover:text-brand-700">
                      {agent.name}
                    </Link>
                    <p className="muted">{agent.role}</p>
                  </div>
                  <Badge
                    value={agent.is_active ? "completed" : "cancelled"}
                    label={agent.is_active ? "فعال" : "غیرفعال"}
                  />
                </div>

                <dl className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-ink-500">مدل</dt>
                    <dd className="ltr text-xs text-ink-800">
                      {agent.model_external_id ?? "انتخاب نشده"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-500">پرامپت</dt>
                    <dd className="ltr text-xs text-ink-800">{agent.system_prompt_key}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-500">بودجه‌ی ماهانه</dt>
                    <dd className="tabular text-ink-800">
                      {agent.monthly_budget_irr ? formatMoney(agent.monthly_budget_irr) : "بدون سقف"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-500">حداکثر توکن</dt>
                    <dd className="tabular text-ink-800">{formatNumber(agent.max_tokens)}</dd>
                  </div>
                </dl>

                <Link href={`/agents/${agent.id}`} className="btn-ghost w-full">
                  تنظیمات ایجنت
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
