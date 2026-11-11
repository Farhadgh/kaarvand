"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { AgentTask } from "@/lib/types";

export function TaskRowActions({
  agentId,
  task,
  canEdit,
}: {
  agentId: string;
  task: AgentTask;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: task.name,
    schedule_cron: task.schedule_cron ?? "0 8 * * *",
    requires_approval: task.requires_approval,
  });

  async function act(key: string, run: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await run();
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function runNow() {
    setBusy("run");
    setError(null);
    setResult(null);
    try {
      const response = await clientFetch<{ text: string; run: { status: string } }>(
        `/agents/${agentId}/tasks/${task.id}/run`,
        { method: "POST" },
      );
      setResult(response.text || `وضعیت: ${response.run.status}`);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    await act("save", () =>
      clientFetch(`/agents/${agentId}/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: form.name,
          schedule_cron: form.schedule_cron,
          requires_approval: form.requires_approval,
        }),
      }),
    );
    setEditing(false);
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex flex-wrap gap-1">
        <button
          className="btn-ghost !px-2 !py-1 text-xs"
          disabled={busy !== null}
          onClick={() => void runNow()}
          title="اجرای فوری همین حالا"
        >
          {busy === "run" ? "…" : "اجرا"}
        </button>
        {canEdit ? (
          <>
            <button
              className="btn-ghost !px-2 !py-1 text-xs"
              disabled={busy !== null}
              onClick={() => setEditing((value) => !value)}
            >
              {editing ? "بستن" : messages.edit}
            </button>
            <button
              className="btn-ghost !px-2 !py-1 text-xs"
              disabled={busy !== null}
              onClick={() =>
                void act("toggle", () =>
                  clientFetch(`/agents/${agentId}/tasks/${task.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ is_active: !task.is_active }),
                  }),
                )
              }
            >
              {task.is_active ? "غیرفعال" : "فعال"}
            </button>
            <button
              className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
              disabled={busy !== null}
              onClick={() => {
                if (!window.confirm(messages.confirmDelete)) return;
                void act("delete", () =>
                  clientFetch(`/agents/${agentId}/tasks/${task.id}`, { method: "DELETE" }),
                );
              }}
            >
              حذف
            </button>
          </>
        ) : null}
      </div>

      {editing ? (
        <div className="mt-1 w-64 space-y-2 rounded-lg bg-ink-50 p-2">
          <Field label="نام">
            <input
              className="input !py-1 text-xs"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
          <Field label="زمان‌بندی (cron)">
            <input
              className="input ltr !py-1 text-xs"
              dir="ltr"
              value={form.schedule_cron}
              onChange={(event) => setForm({ ...form, schedule_cron: event.target.value })}
            />
          </Field>
          <label className="flex items-center gap-2 text-xs text-ink-600">
            <input
              type="checkbox"
              checked={form.requires_approval}
              onChange={(event) => setForm({ ...form, requires_approval: event.target.checked })}
            />
            نیازمند تأیید انسانی
          </label>
          <button className="btn-primary !py-1 text-xs" disabled={busy !== null} onClick={() => void save()}>
            {busy === "save" ? "…" : messages.save}
          </button>
        </div>
      ) : null}

      {result ? (
        <p className="max-w-xs text-[11px] text-emerald-700">اجرا شد: {result.slice(0, 120)}</p>
      ) : null}
      {error ? <p className="max-w-xs text-[11px] text-rose-600">{error}</p> : null}
    </div>
  );
}
