"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { TaskRow } from "@/components/task-row";
import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import type { AgentTask, User } from "@/lib/types";

export function AgentTasksCard({
  agentId,
  tasks,
  promptKeys,
  me,
}: {
  agentId: string;
  tasks: AgentTask[];
  promptKeys: string[];
  me: User;
}) {
  const router = useRouter();
  const canEdit = me.role === "admin";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    prompt_key: promptKeys[0] ?? "",
    trigger_type: "schedule",
    schedule_cron: "0 8 * * *",
    requires_approval: false,
  });

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await clientFetch(`/agents/${agentId}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          prompt_key: form.prompt_key || null,
          prompt_template: form.prompt_key ? null : "خلاصه‌ی وضعیت امروز را آماده کن.",
          trigger_type: form.trigger_type,
          schedule_cron: form.trigger_type === "schedule" ? form.schedule_cron : null,
          requires_approval: form.requires_approval,
        }),
      });
      setForm({ ...form, name: "" });
      setOpen(false);
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
        title="وظایف و زمان‌بندی"
        subtitle="cron در منطقه‌ی زمانی سازمان؛ هر اجرا در صفحه‌ی اجراها ثبت می‌شود"
        action={
          canEdit ? (
            <button className="btn-primary" onClick={() => setOpen((value) => !value)}>
              {open ? "بستن فرم" : "وظیفه‌ی جدید"}
            </button>
          ) : null
        }
      />
      <div className="card-body space-y-4">
        {error ? <ErrorBox message={error} /> : null}

        {open && canEdit ? (
          <form className="grid grid-cols-1 gap-3 md:grid-cols-5" onSubmit={create}>
            <Field label="نام وظیفه">
              <input
                className="input"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </Field>
            <Field label="پرامپت">
              <select
                className="input ltr"
                dir="ltr"
                value={form.prompt_key}
                onChange={(event) => setForm({ ...form, prompt_key: event.target.value })}
              >
                {(promptKeys.length ? promptKeys : [""]).map((key) => (
                  <option key={key} value={key}>
                    {key || "— پرامپت پیش‌فرض —"}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="نوع تریگر">
              <select
                className="input"
                value={form.trigger_type}
                onChange={(event) => setForm({ ...form, trigger_type: event.target.value })}
              >
                <option value="schedule">زمان‌بندی</option>
                <option value="manual">دستی</option>
              </select>
            </Field>
            <Field label="زمان‌بندی (cron)" hint="0 8 * * * = هر روز ۸ صبح">
              <input
                className="input ltr"
                dir="ltr"
                value={form.schedule_cron}
                disabled={form.trigger_type !== "schedule"}
                onChange={(event) => setForm({ ...form, schedule_cron: event.target.value })}
              />
            </Field>
            <div className="flex flex-col justify-end gap-2">
              <label className="flex items-center gap-2 text-xs text-ink-600">
                <input
                  type="checkbox"
                  checked={form.requires_approval}
                  onChange={(event) =>
                    setForm({ ...form, requires_approval: event.target.checked })
                  }
                />
                نیازمند تأیید
              </label>
              <button className="btn-primary" disabled={busy || !form.name.trim()}>
                {busy ? "…" : "افزودن"}
              </button>
            </div>
          </form>
        ) : null}

        {tasks.length === 0 ? (
          <p className="muted">هنوز وظیفه‌ای تعریف نشده است.</p>
        ) : (
          <div className="table-wrapper">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">وظیفه</th>
                  <th className="th">زمان‌بندی</th>
                  <th className="th">اجرای بعدی</th>
                  <th className="th">آخرین اجرا</th>
                  <th className="th">وضعیت</th>
                  <th className="th">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <TaskRow key={task.id} agentId={agentId} task={task} canEdit={canEdit} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}
