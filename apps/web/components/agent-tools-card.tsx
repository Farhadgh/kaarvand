"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, Card, CardHeader, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages, permissionLabels } from "@/lib/copy";
import type { Tool, User } from "@/lib/types";

type Binding = { tool_id: string; permission_level: string; is_enabled: boolean };

export function AgentToolsCard({
  agentId,
  tools,
  bindings,
  me,
}: {
  agentId: string;
  tools: Tool[];
  bindings: Binding[];
  me: User;
}) {
  const router = useRouter();
  const canEdit = me.role === "owner" || me.role === "admin";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    for (const binding of bindings) map[binding.tool_id] = binding.permission_level;
    return map;
  });

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await clientFetch(`/agents/${agentId}/tools`, {
        method: "PUT",
        body: JSON.stringify(
          Object.entries(selected).map(([toolId, level]) => ({
            tool_id: toolId,
            permission_level: level,
          })),
        ),
      });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="ابزارهای مجاز"
        subtitle="سطح هر ابزار مستقل است: خودکار، با تأیید یا ممنوع"
        action={
          canEdit ? (
            <button className="btn-primary" onClick={() => void save()} disabled={busy}>
              {busy ? "…" : messages.save}
            </button>
          ) : null
        }
      />
      <div className="card-body">
        {error ? <ErrorBox message={error} /> : null}
        {tools.length === 0 ? (
          <p className="muted">هنوز ابزاری تعریف نشده است.</p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {tools.map((tool) => (
              <li key={tool.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink-900">{tool.name_fa}</span>
                    <Badge value={tool.risk_level} />
                    {tool.org_id === null ? (
                      <span className="text-[11px] text-ink-400">سراسری</span>
                    ) : null}
                  </div>
                  <div className="ltr text-xs text-ink-400">{tool.slug}</div>
                </div>
                <select
                  className="input w-36"
                  value={selected[tool.id] ?? ""}
                  disabled={!canEdit}
                  onChange={(event) => {
                    const next = { ...selected };
                    if (!event.target.value) delete next[tool.id];
                    else next[tool.id] = event.target.value;
                    setSelected(next);
                  }}
                >
                  <option value="">— متصل نیست —</option>
                  <option value="auto">{permissionLabels.auto}</option>
                  <option value="confirm">{permissionLabels.confirm}</option>
                  <option value="deny">{permissionLabels.deny}</option>
                </select>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
