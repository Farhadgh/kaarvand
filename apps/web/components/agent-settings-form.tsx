"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { Agent, User } from "@/lib/types";

export function AgentSettingsForm({
  agent,
  models,
  promptKeys,
  me,
}: {
  agent: Agent;
  models: { id: string; label: string }[];
  promptKeys: string[];
  me: User;
}) {
  const router = useRouter();
  const canEdit = me.role === "owner" || me.role === "admin";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: agent.name,
    role: agent.role,
    system_prompt_key: agent.system_prompt_key,
    model_id: agent.model_id ?? "",
    temperature: agent.temperature,
    max_tokens: String(agent.max_tokens),
    monthly_budget_irr: agent.monthly_budget_irr ? String(agent.monthly_budget_irr) : "",
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await clientFetch(`/agents/${agent.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: form.name,
          role: form.role,
          system_prompt_key: form.system_prompt_key,
          model_id: form.model_id || null,
          temperature: form.temperature,
          max_tokens: Number(form.max_tokens || 0),
          monthly_budget_irr: form.monthly_budget_irr ? Number(form.monthly_budget_irr) : null,
        }),
      });
      setNotice("تنظیمات ذخیره شد.");
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title="تنظیمات ایجنت" subtitle="نام، پرامپت، مدل و بودجه" />
      <form className="card-body grid grid-cols-1 gap-4 md:grid-cols-2" onSubmit={submit}>
        {error ? (
          <div className="md:col-span-2">
            <ErrorBox message={error} />
          </div>
        ) : null}
        {notice ? (
          <p className="md:col-span-2 text-sm text-emerald-700">{notice}</p>
        ) : null}

        <Field label="نام">
          <input
            className="input"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label="نقش">
          <input
            className="input"
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value })}
          />
        </Field>
        <Field label="پرامپت (کلید)">
          <select
            className="input ltr"
            dir="ltr"
            value={form.system_prompt_key}
            onChange={(event) => setForm({ ...form, system_prompt_key: event.target.value })}
          >
            {promptKeys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </Field>
        <Field label="مدل">
          <select
            className="input"
            value={form.model_id}
            onChange={(event) => setForm({ ...form, model_id: event.target.value })}
          >
            <option value="">— انتخاب نشده —</option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="دما (۰ تا ۲)">
          <input
            className="input ltr"
            dir="ltr"
            value={form.temperature}
            onChange={(event) => setForm({ ...form, temperature: event.target.value })}
          />
        </Field>
        <Field label="حداکثر توکن">
          <input
            className="input ltr"
            dir="ltr"
            value={form.max_tokens}
            onChange={(event) =>
              setForm({ ...form, max_tokens: event.target.value.replace(/\D/g, "") })
            }
          />
        </Field>
        <Field label="سقف بودجه‌ی ماهانه (ریال)" hint="خالی = بدون سقف">
          <input
            className="input ltr"
            dir="ltr"
            value={form.monthly_budget_irr}
            onChange={(event) =>
              setForm({ ...form, monthly_budget_irr: event.target.value.replace(/\D/g, "") })
            }
          />
        </Field>
        <div className="flex items-end justify-end">
          <button className="btn-primary" disabled={!canEdit || busy}>
            {busy ? "در حال ذخیره…" : messages.save}
          </button>
        </div>
      </form>
    </Card>
  );
}
