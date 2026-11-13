"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clientFetch, messageOf } from "@/lib/api";

/** Reconciliation for a payment whose gateway callback never arrived. */
export function PaymentRowActions({ paymentId }: { paymentId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      await clientFetch(`/payments/${paymentId}/verify`, { method: "POST" });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        className="btn-ghost !px-2 !py-1 text-xs"
        disabled={busy}
        onClick={() => void verify()}
      >
        {busy ? "…" : "استعلام از درگاه"}
      </button>
      {error ? <span className="text-[11px] text-rose-600">{error}</span> : null}
    </div>
  );
}
