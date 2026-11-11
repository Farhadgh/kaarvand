"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clientFetch, messageOf } from "@/lib/api";
import { messages } from "@/lib/copy";
import type { Provider } from "@/lib/types";

export function ProviderActions({
  provider,
  canEdit,
}: {
  provider: Provider;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(key: string, task: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await task();
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  const button = (
    key: string,
    label: string,
    task: () => Promise<unknown>,
    tone = "btn-ghost",
  ) => (
    <button
      key={key}
      className={`${tone} !px-2 !py-1 text-xs`}
      disabled={!canEdit || busy !== null}
      onClick={() => void run(key, task)}
      title={label}
    >
      {busy === key ? "…" : label}
    </button>
  );

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {button("test", "تست", () =>
          clientFetch(`/providers/${provider.id}/test`, { method: "POST" }),
        )}
        {button("models", "سینک مدل", () =>
          clientFetch(`/providers/${provider.id}/sync-models`, { method: "POST" }),
        )}
        {button("prices", "سینک قیمت", () =>
          clientFetch(`/providers/${provider.id}/sync-prices`, { method: "POST" }),
        )}
        {button("toggle", provider.is_enabled ? "غیرفعال" : "فعال", () =>
          clientFetch(`/providers/${provider.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_enabled: !provider.is_enabled }),
          }),
        )}
        <button
          className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
          disabled={!canEdit || busy !== null}
          onClick={() => {
            if (!window.confirm(messages.confirmDelete)) return;
            void run("delete", () =>
              clientFetch(`/providers/${provider.id}`, { method: "DELETE" }),
            );
          }}
        >
          {busy === "delete" ? "…" : messages.delete}
        </button>
      </div>
      {error ? <span className="text-[11px] text-rose-600">{error}</span> : null}
    </div>
  );
}
