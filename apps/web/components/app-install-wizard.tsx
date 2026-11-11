"use client";

import { useEffect, useState } from "react";

import { AppTile } from "@/components/app-icons";
import { Badge, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages, permissionLabels, runtimeLabels } from "@/lib/copy";
import type { AppInstallResult, CatalogAppDetail, Device } from "@/lib/types";

type AgentOption = { id: string; name: string };

const warningCopy: Record<string, string> = {
  app_not_granted:
    "برنامه روی دستگاه شناسایی شده ولی هنوز «مجاز» نشده است؛ از صفحه‌ی دستگاه‌ها مجازش کنید.",
};

export function AppInstallWizard({
  app,
  agents,
  devices,
  defaultAgentId,
  onClose,
  onInstalled,
}: {
  app: CatalogAppDetail | null;
  agents: AgentOption[];
  devices: Device[];
  defaultAgentId?: string;
  onClose: () => void;
  onInstalled: () => void;
}) {
  const [agentId, setAgentId] = useState(defaultAgentId ?? "");
  const [deviceId, setDeviceId] = useState("");
  const [permission, setPermission] = useState("confirm");
  const [values, setValues] = useState<Record<string, string>>({});
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    setAgentId(defaultAgentId ?? agents[0]?.id ?? "");
    setDeviceId("");
    setPermission("confirm");
    setValues({});
    setForce(false);
    setError(null);
    setWarnings([]);
  }, [app, agents, defaultAgentId]);

  if (!app) return null;

  const secretFields = app.credentials.filter((cred) => cred.secret);
  const plainFields = app.credentials.filter((cred) => !cred.secret);

  async function submit() {
    if (!app) return;
    setBusy(true);
    setError(null);
    setWarnings([]);
    try {
      const secret = secretFields
        .map((cred) => values[cred.key] ?? "")
        .find((value) => value.trim().length > 0);
      const variables: Record<string, string> = {};
      for (const cred of plainFields) {
        const value = (values[cred.key] ?? "").trim();
        if (value) variables[cred.key] = value;
      }
      const result = await clientFetch<AppInstallResult>(`/apps/${app.slug}/install`, {
        method: "POST",
        body: JSON.stringify({
          agent_id: agentId,
          permission_level: permission,
          device_id: deviceId || undefined,
          variables,
          secret,
          force,
        }),
      });
      if (result.warnings?.length) {
        setWarnings(result.warnings.map((code) => warningCopy[code] ?? code));
      } else {
        onInstalled();
        onClose();
      }
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4">
      <div className="my-8 w-full max-w-2xl rounded-xl2 bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
          <div className="flex items-center gap-3">
            <AppTile icon={app.icon} color={app.color} name={app.name_fa} />
            <div>
              <h2 className="text-base font-bold text-ink-900">اتصال {app.name_fa}</h2>
              <p className="muted mt-0.5">
                {runtimeLabels[app.runtime] ?? app.runtime}
                {app.vendor ? ` · ${app.vendor}` : ""}
              </p>
            </div>
          </div>
          <button className="btn-ghost !px-2 !py-1 text-xs" onClick={onClose}>
            بستن
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          {app.setup_fa ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-800">
              <p className="font-medium">پیش‌نیازها</p>
              <p>{app.setup_fa}</p>
              {app.docs_url ? (
                <a
                  className="ltr mt-1 inline-block underline"
                  href={app.docs_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {app.docs_url}
                </a>
              ) : null}
            </div>
          ) : null}

          {error ? <ErrorBox message={error} /> : null}
          {warnings.length ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {warnings.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          ) : null}

          <Field label="ایجنت">
            <select
              className="input"
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
            >
              <option value="">— انتخاب ایجنت —</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </Field>

          {app.requires_device ? (
            <>
              <Field
                label="دستگاه"
                hint="این برنامه روی رایانه‌ی مشتری اجرا می‌شود؛ کانکتور باید آنلاین باشد."
              >
                <select
                  className="input"
                  value={deviceId}
                  onChange={(event) => setDeviceId(event.target.value)}
                >
                  <option value="">— انتخاب دستگاه —</option>
                  {devices.map((device) => (
                    <option key={device.id} value={device.id}>
                      {device.name} · {device.status}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="flex items-center gap-2 text-xs text-ink-600">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(event) => setForce(event.target.checked)}
                />
                برنامه روی دستگاه شناسایی نشده؛ با این حال نصب کن
              </label>
            </>
          ) : null}

          {plainFields.map((cred) => (
            <Field key={cred.key} label={cred.label_fa}>
              <input
                className="input ltr"
                dir="ltr"
                placeholder={cred.placeholder ?? ""}
                value={values[cred.key] ?? ""}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, [cred.key]: event.target.value }))
                }
              />
            </Field>
          ))}

          {secretFields.map((cred) => (
            <Field
              key={cred.key}
              label={cred.label_fa}
              hint="رمزنگاری‌شده ذخیره می‌شود و دیگر نمایش داده نمی‌شود."
            >
              <input
                className="input ltr"
                dir="ltr"
                type="password"
                autoComplete="off"
                value={values[cred.key] ?? ""}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, [cred.key]: event.target.value }))
                }
              />
            </Field>
          ))}

          <Field label="سطح دسترسی ایجنت به این برنامه">
            <select
              className="input"
              value={permission}
              onChange={(event) => setPermission(event.target.value)}
            >
              <option value="confirm">{permissionLabels.confirm} (پیشنهادی)</option>
              <option value="auto">{permissionLabels.auto}</option>
              <option value="deny">{permissionLabels.deny}</option>
            </select>
          </Field>

          <div className="flex items-center gap-2 text-xs text-ink-500">
            <Badge value={app.risk_level} />
            <span>سطح ریسک پیش‌فرض این برنامه</span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-ink-100 px-5 py-3">
          <span className="text-xs text-ink-400">
            {app.installed_agents > 0
              ? `تاکنون برای ${app.installed_agents} ایجنت متصل شده است`
              : "اولین اتصال این برنامه"}
          </span>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={onClose} disabled={busy}>
              {messages.cancel}
            </button>
            <button
              className="btn-primary"
              onClick={() => void submit()}
              disabled={busy || !agentId || (app.requires_device && !deviceId)}
            >
              {busy ? "در حال اتصال…" : "اتصال برنامه"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
