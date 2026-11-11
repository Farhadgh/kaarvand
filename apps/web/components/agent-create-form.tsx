"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";

const ROLE_TEMPLATES = [
  { key: "agent.system.default", label: "دستیار عمومی" },
  { key: "agent.system.accountant", label: "حسابدار" },
  { key: "agent.system.sales", label: "فروشنده" },
  { key: "agent.system.receptionist", label: "منشی / پاسخگو" },
];

export function AgentCreateForm({
  models,
  canEdit,
}: {
  models: { id: string; label: string }[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [role, setRole] = useState("assistant");
  const [promptKey, setPromptKey] = useState(ROLE_TEMPLATES[0].key);
  const [modelId, setModelId] = useState(models[0]?.id ?? "");
  const [budget, setBudget] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await clientFetch<{ id: string }>("/agents", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          role,
          system_prompt_key: promptKey,
          model_id: modelId || null,
          monthly_budget_irr: budget ? Number(budget) : null,
        }),
      });
      router.push(`/agents/${created.id}`);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  if (!canEdit) return null;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button className="btn-primary" onClick={() => setOpen((value) => !value)}>
          {open ? "بستن فرم" : "ایجنت جدید"}
        </button>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {open ? (
        <form
          className="card card-body grid grid-cols-1 gap-4 md:grid-cols-2"
          onSubmit={submit}
        >
          <Field label="نام ایجنت">
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="مثلاً حسابدار ارشد"
              required
            />
          </Field>

          <Field label="الگوی نقش" hint="پرامپت را بعداً در تب پرامپت ویرایش می‌کنید">
            <select
              className="input"
              value={promptKey}
              onChange={(event) => {
                setPromptKey(event.target.value);
                setRole(event.target.value.split(".").pop() ?? "assistant");
              }}
            >
              {ROLE_TEMPLATES.map((template) => (
                <option key={template.key} value={template.key}>
                  {template.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="مدل" hint={models.length === 0 ? "ابتدا پروایدر را سینک کنید" : undefined}>
            <select className="input" value={modelId} onChange={(event) => setModelId(event.target.value)}>
              <option value="">— بدون مدل —</option>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="سقف بودجه‌ی ماهانه (تومان)" hint="خالی = بدون سقف">
            <input
              className="input ltr"
              dir="ltr"
              inputMode="numeric"
              value={budget}
              onChange={(event) => setBudget(event.target.value.replace(/[^0-9]/g, ""))}
            />
          </Field>

          <div className="flex justify-end gap-2 md:col-span-2">
            <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
              {busy ? "در حال ساخت…" : "ساخت ایجنت"}
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
