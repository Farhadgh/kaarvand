import Link from "next/link";
import { notFound } from "next/navigation";

import { AgentAppsCard } from "@/components/agent-apps-card";
import { AgentSettingsForm } from "@/components/agent-settings-form";
import { AgentTasksCard } from "@/components/agent-tasks-card";
import { AgentToolsCard } from "@/components/agent-tools-card";
import { Card, CardHeader } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { ApiError } from "@/lib/api-errors";
import type {
  Agent,
  AgentTask,
  CatalogApp,
  Model,
  Prompt,
  RenderedPrompt,
  Tool,
  User,
} from "@/lib/types";

export const dynamic = "force-dynamic";

type Binding = { tool_id: string; permission_level: string; is_enabled: boolean };

export default async function AgentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let agent: Agent;
  try {
    agent = await serverFetch<Agent>(`/agents/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const [models, tools, bindings, tasks, prompts, me, prompt, catalog] = await Promise.all([
    serverFetch<Model[]>("/models?capability=tools&limit=200").catch(() => [] as Model[]),
    serverFetch<Tool[]>("/tools?enabled_only=false"),
    serverFetch<Binding[]>(`/agents/${id}/tools`).catch(() => [] as Binding[]),
    serverFetch<AgentTask[]>(`/agents/${id}/tasks`).catch(() => [] as AgentTask[]),
    serverFetch<Prompt[]>("/prompts").catch(() => [] as Prompt[]),
    serverFetch<User>("/auth/me"),
    serverFetch<RenderedPrompt>(`/agents/${id}/prompt`).catch(() => null),
    serverFetch<CatalogApp[]>("/apps").catch(() => [] as CatalogApp[]),
  ]);

  const modelOptions = models.map((model) => ({
    id: model.id,
    label: model.display_name_fa ?? model.external_id,
  }));
  const promptKeys = Array.from(new Set(prompts.map((item) => item.key))).sort();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/agents" className="text-sm text-brand-700 hover:underline">
            ← بازگشت به ایجنت‌ها
          </Link>
          <h1 className="page-title mt-1">{agent.name}</h1>
          <p className="muted">
            {agent.role} · مدل {agent.model_external_id ?? "انتخاب‌نشده"} · پرامپت{" "}
            {agent.system_prompt_key}
          </p>
        </div>
        <Link href="/playground" className="btn-primary">
          اجرا در آزمایشگاه
        </Link>
      </div>

      <AgentSettingsForm
        agent={agent}
        models={modelOptions}
        promptKeys={promptKeys.length ? promptKeys : [agent.system_prompt_key]}
        me={me}
      />

      <AgentAppsCard
        agentId={agent.id}
        tools={tools}
        bindings={bindings}
        catalog={catalog}
        me={me}
      />

      <AgentToolsCard agentId={agent.id} tools={tools} bindings={bindings} me={me} />

      <AgentTasksCard
        agentId={agent.id}
        tasks={tasks}
        promptKeys={promptKeys.length ? promptKeys : [agent.system_prompt_key]}
        me={me}
      />

      <Card>
        <CardHeader
          title="پیش‌نمایش پرامپت مؤثر"
          subtitle={prompt ? `نسخه ${prompt.version}` : "پرامپت قابل رندر نیست"}
        />
        <div className="card-body">
          <pre className="whitespace-pre-wrap rounded-lg bg-ink-50 p-3 text-sm leading-7">
            {prompt?.rendered ?? "—"}
          </pre>
          {prompt?.missing?.length ? (
            <p className="mt-2 text-xs text-amber-700">
              متغیرهای بدون مقدار: {prompt.missing.join("، ")}
            </p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
