"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Logout is a `POST` to the route handler, so it cannot be a plain `<a href>`.
 * Used where the panel is shown as a dead end (a customer account signed in to
 * the admin console): the only way out must actually work.
 */
export function LogoutButton({
  children,
  className = "btn-primary",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <button type="button" className={className} onClick={submit} disabled={busy}>
      {busy ? "در حال خروج…" : children}
    </button>
  );
}
