"use client";

export type PlaygroundEvent = { event: string; data: Record<string, unknown> };

export function EventList({ events }: { events: PlaygroundEvent[] }) {
  return (
    <ul className="max-h-[32rem] space-y-1 overflow-auto p-3 text-xs">
      {events.length === 0 ? (
        <li className="text-ink-400">—</li>
      ) : (
        events.map((item, index) => (
          <li key={`${item.event}-${index}`} className="flex items-start gap-2">
            <span className="ltr rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-700">
              {item.event}
            </span>
            <span className="line-clamp-2 text-ink-500">
              {String(item.data.text ?? item.data.tool ?? item.data.code ?? "")}
            </span>
          </li>
        ))
      )}
    </ul>
  );
}

export function ApprovalCard({
  approval,
  busy,
  onApprove,
  onDismiss,
}: {
  approval: Record<string, unknown>;
  busy: boolean;
  onApprove: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="rounded-xl2 border border-amber-300 bg-amber-50 p-4">
      <p className="font-medium text-amber-900">
        ایجنت می‌خواهد ابزار «{String(approval.tool ?? "")}» را اجرا کند (ریسک{" "}
        {String(approval.risk ?? "—")})
      </p>
      <pre className="ltr mt-2 max-h-40 overflow-auto rounded-lg bg-white/70 p-2 text-xs">
        {JSON.stringify(approval.arguments ?? {}, null, 2)}
      </pre>
      <div className="mt-3 flex gap-2">
        <button className="btn-primary" onClick={onApprove} disabled={busy}>
          تأیید و ادامه
        </button>
        <button className="btn-ghost" onClick={onDismiss}>
          رد
        </button>
      </div>
    </div>
  );
}
