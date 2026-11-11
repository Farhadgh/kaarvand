"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clientFetch, messageOf } from "@/lib/api";
import type { Run } from "@/lib/types";

export function RunActions({ run }: { run: Run }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(path: string, body?: unknown) {
    setBusy(path);
    setError(null);
    try {
      await clientFetch(path, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {run.status === "waiting_approval" ? (
          <>
            <button
              className="btn-primary !px-2 !py-1 text-xs"
              disabled={busy !== null}
              onClick={() => void act(`/runs/${run.id}/approve`, { stream: false })}
            >
              تأیید
            </button>
            <button
              className="btn-ghost !px-2 !py-1 text-xs"
              disabled={busy !== null}
              onClick={() => void act(`/runs/${run.id}/cancel`)}
            >
              رد
            </button>
          </>
        ) : null}
        {["running", "queued", "waiting_approval"].includes(run.status) ? (
          <button
            className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
            disabled={busy !== null}
            onClick={() => void act(`/runs/${run.id}/cancel`)}
          >
            لغو
          </button>
        ) : null}
      </div>
      {error ? <span className="text-[11px] text-rose-600">{error}</span> : null}
    </div>
  );
}
