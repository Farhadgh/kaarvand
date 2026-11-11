"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clientFetch, messageOf } from "@/lib/api";
import type { User } from "@/lib/types";

export function UserRowActions({ user }: { user: User }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(key: string, task: () => Promise<unknown>) {
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

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        <button
          className="btn-ghost !px-2 !py-1 text-xs"
          disabled={busy !== null}
          onClick={() => {
            const password = window.prompt("رمز عبور جدید (حداقل ۸ کاراکتر):");
            if (!password) return;
            void act("reset", () =>
              clientFetch(`/users/${user.id}/reset-password`, {
                method: "POST",
                body: JSON.stringify({ password }),
              }),
            );
          }}
        >
          رمز جدید
        </button>
        <button
          className="btn-ghost !px-2 !py-1 text-xs"
          disabled={busy !== null}
          onClick={() =>
            void act("toggle", () =>
              clientFetch(`/users/${user.id}`, {
                method: "PATCH",
                body: JSON.stringify({ is_active: !user.is_active }),
              }),
            )
          }
        >
          {user.is_active ? "غیرفعال" : "فعال"}
        </button>
      </div>
      {error ? <span className="text-[11px] text-rose-600">{error}</span> : null}
    </div>
  );
}
