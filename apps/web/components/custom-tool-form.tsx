"use client";

import { useState } from "react";

import { ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { Tool } from "@/lib/types";

const HTTP_EXAMPLE = {
  method: "POST",
  url: "https://api.example.com/v1/items",
  allowed_domains: ["api.example.com"],
  headers: { "Content-Type": "application/json" },
  body: { name: "{{name}}" },
  auth: { type: "bearer" },
  timeout: 20,
};

const ACTION_EXAMPLE = [
  { op: "app.launch", app: "excel" },
  { op: "wait", seconds: 2 },
  { op: "screenshot", save_as: "artifacts/{{run_id}}.png" },
];

export function CustomToolForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [kind, setKind] = useState<"http" | "connector">("http");
  const [nameFa, setNameFa] = useState("");
  const [slug, setSlug] = useState("");
  const [category, setCategory] = useState("general");
  const [risk, setRisk] = useState("medium");
  const [approval, setApproval] = useState("confirm");
  const [secret, setSecret] = useState("");
  const [description, setDescription] = useState("");
  const [configText, setConfigText] = useState(JSON.stringify(HTTP_EXAMPLE, null, 2));
  const [actionsText, setActionsText] = useState(JSON.stringify(ACTION_EXAMPLE, null, 1));
  const [inputText, setInputText] = useState(
    JSON.stringify(
      { type: "object", properties: { text: { type: "string" } }, required: ["text"] },
      null,
      2,
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function switchKind(next: "http" | "connector") {
    setKind(next);
    setConfigText(JSON.stringify(next === "http" ? HTTP_EXAMPLE : {}, null, 2));
    setActionsText(JSON.stringify(next === "connector" ? ACTION_EXAMPLE : [], null, 1));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        slug: slug.trim(),
        name_fa: nameFa.trim(),
        description_fa: description.trim() || null,
        kind,
        input_schema: JSON.parse(inputText || "{}"),
        config: kind === "http" ? JSON.parse(configText || "{}") : {},
        actions: kind === "connector" ? JSON.parse(actionsText || "[]") : [],
        risk_level: risk,
        approval_policy: approval,
        category,
        is_enabled: true,
        secret: secret.trim() || null,
        secret_label: secret.trim() ? "کلید ابزار" : null,
      };
      await clientFetch<Tool>("/tools", { method: "POST", body: JSON.stringify(payload) });
      onCreated();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4">
      <div className="my-8 w-full max-w-2xl rounded-xl2 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
          <h2 className="text-base font-bold text-ink-900">افزودن ابزار من</h2>
          <button className="btn-ghost !px-2 !py-1 text-xs" onClick={onClose}>
            بستن
          </button>
        </div>

        <div className="space-y-3 px-5 py-4">
          {error ? <ErrorBox message={error} /> : null}

          <div className="flex gap-2">
            <button
              className={`btn-ghost !py-1 text-xs ${
                kind === "http" ? "!border-brand-400 !text-brand-700" : ""
              }`}
              onClick={() => switchKind("http")}
            >
              HTTP (سرور)
            </button>
            <button
              className={`btn-ghost !py-1 text-xs ${
                kind === "connector" ? "!border-brand-400 !text-brand-700" : ""
              }`}
              onClick={() => switchKind("connector")}
            >
              اسکریپت روی دستگاه
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="نام فارسی">
              <input
                className="input"
                value={nameFa}
                onChange={(event) => setNameFa(event.target.value)}
                placeholder="مثلاً ارسال پیام به سامانه‌ی داخلی"
              />
            </Field>
            <Field label="شناسه (slug)" hint="حروف کوچک، عدد، نقطه و خط تیره">
              <input
                className="input ltr"
                dir="ltr"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="mycompany.internal.send"
              />
            </Field>
          </div>

          <Field label="توضیح برای مدل">
            <input
              className="input"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="دسته">
              <select
                className="input"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="general">عمومی</option>
                <option value="social">شبکه اجتماعی</option>
                <option value="office">آفیس</option>
                <option value="productivity">بهره‌وری</option>
                <option value="devices">دستگاه</option>
                <option value="web">وب</option>
                <option value="dev">توسعه</option>
              </select>
            </Field>
            <Field label="ریسک">
              <select
                className="input"
                value={risk}
                onChange={(event) => setRisk(event.target.value)}
              >
                <option value="low">کم</option>
                <option value="medium">متوسط</option>
                <option value="high">زیاد</option>
              </select>
            </Field>
            <Field label="سیاست اجرا">
              <select
                className="input"
                value={approval}
                onChange={(event) => setApproval(event.target.value)}
              >
                <option value="confirm">با تأیید</option>
                <option value="auto">خودکار</option>
                <option value="deny">ممنوع</option>
              </select>
            </Field>
          </div>

          <Field label="اعتبارنامه (اختیاری)" hint="رمزنگاری‌شده ذخیره می‌شود؛ در قالب با {{secret}} قابل استفاده است.">
            <input
              className="input ltr"
              dir="ltr"
              type="password"
              autoComplete="off"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
            />
          </Field>

          <Field label="اسکیمای ورودی (JSON Schema)">
            <textarea
              className="input ltr min-h-24 font-mono text-xs"
              dir="ltr"
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
            />
          </Field>

          {kind === "http" ? (
            <Field label="پیکربندی درخواست (JSON)" hint="method, url, allowed_domains, headers, body, auth, timeout">
              <textarea
                className="input ltr min-h-40 font-mono text-xs"
                dir="ltr"
                value={configText}
                onChange={(event) => setConfigText(event.target.value)}
              />
            </Field>
          ) : (
            <Field label="اسکریپت اقدام (JSON آرایه)" hint="گام‌ها روی دستگاه مشتری اجرا می‌شوند">
              <textarea
                className="input ltr min-h-40 font-mono text-xs"
                dir="ltr"
                value={actionsText}
                onChange={(event) => setActionsText(event.target.value)}
              />
            </Field>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-ink-100 px-5 py-3">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>
            {messages.cancel}
          </button>
          <button
            className="btn-primary"
            onClick={() => void submit()}
            disabled={busy || !nameFa.trim() || !slug.trim()}
          >
            {busy ? "در حال ذخیره…" : messages.create}
          </button>
        </div>
      </div>
    </div>
  );
}
