"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, Card, CardHeader, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { Prompt, PromptVersion } from "@/lib/types";

export function PromptEditor({
  prompt,
  versions,
  canEdit,
}: {
  prompt: Prompt;
  versions: PromptVersion[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [template, setTemplate] = useState(prompt.template);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const readOnly = prompt.org_id === null || !canEdit;

  async function act(key: string, task: () => Promise<unknown>, success: string) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await task();
      setNotice(success);
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  async function save(publish: boolean) {
    await act(
      publish ? "publish" : "save",
      () =>
        clientFetch(`/prompts/${prompt.id}`, {
          method: "PUT",
          body: JSON.stringify({ template, note: note || null, publish }),
        }),
      publish ? "نسخه‌ی جدید منتشر شد." : "پیش‌نویس ذخیره شد.",
    );
  }

  async function fork() {
    await act(
      "fork",
      () =>
        clientFetch("/prompts", {
          method: "POST",
          body: JSON.stringify({
            key: prompt.key,
            title_fa: prompt.title_fa,
            template,
            kind: prompt.kind,
            locale: prompt.locale,
            publish: true,
          }),
        }),
      "نسخه‌ی سازمانی ساخته شد (اولویت بالاتر از سراسری).",
    );
  }

  return (
    <Card>
      <CardHeader
        title={prompt.title_fa}
        subtitle={`${prompt.key} · نسخه ${formatNumber(prompt.current_version)}`}
        action={<Badge value={prompt.status} />}
      />

      <div className="card-body space-y-3">
        {error ? <ErrorBox message={error} /> : null}
        {notice ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        {prompt.org_id === null ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            این پرامپت سراسری است و ویرایش نمی‌شود؛ برای تغییر، نسخه‌ی سازمانی بسازید.
          </div>
        ) : null}

        <textarea
          className="input min-h-64 font-mono text-[13px] leading-6"
          value={template}
          disabled={readOnly}
          onChange={(event) => setTemplate(event.target.value)}
        />

        <div className="flex flex-wrap items-center gap-2">
          <input
            className="input max-w-xs"
            placeholder="یادداشت نسخه (اختیاری)"
            value={note}
            disabled={readOnly}
            onChange={(event) => setNote(event.target.value)}
          />
          <button
            className="btn-ghost"
            disabled={readOnly || busy !== null}
            onClick={() => void save(false)}
          >
            {busy === "save" ? "…" : "ذخیره‌ی پیش‌نویس"}
          </button>
          <button
            className="btn-primary"
            disabled={readOnly || busy !== null}
            onClick={() => void save(true)}
          >
            {busy === "publish" ? "…" : "ذخیره و انتشار"}
          </button>
          {prompt.org_id === null && canEdit ? (
            <button className="btn-ghost" disabled={busy !== null} onClick={() => void fork()}>
              {busy === "fork" ? "…" : "ساخت نسخه‌ی سازمانی"}
            </button>
          ) : null}
        </div>

        <p className="muted">
          متغیرها: {prompt.variables.length ? prompt.variables.join("، ") : "بدون متغیر"}
        </p>
      </div>

      <div className="border-t border-ink-100 px-5 py-4">
        <h3 className="mb-2 text-sm font-bold text-ink-800">تاریخچه‌ی نسخه‌ها</h3>
        {versions.length === 0 ? (
          <p className="muted">نسخه‌ای ثبت نشده است.</p>
        ) : (
          <ul className="divide-y divide-ink-100 text-sm">
            {versions.map((version) => (
              <li key={version.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div>
                  <span className="font-medium text-ink-900">نسخه {formatNumber(version.version)}</span>
                  <span className="text-xs text-ink-400"> · {formatDateTime(version.created_at)}</span>
                  {version.note ? <p className="text-xs text-ink-500">{version.note}</p> : null}
                </div>
                {canEdit && prompt.org_id !== null && version.version !== prompt.current_version ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs"
                    disabled={busy !== null}
                    onClick={() =>
                      void act(
                        `rollback-${version.version}`,
                        () =>
                          clientFetch(`/prompts/${prompt.id}/rollback`, {
                            method: "POST",
                            body: JSON.stringify({ version: version.version }),
                          }),
                        `بازگشت به نسخه ${version.version} انجام شد.`,
                      )
                    }
                  >
                    بازگردانی
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
