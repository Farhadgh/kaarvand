"use client";

import { useRef, useState } from "react";

import { ApprovalCard, EventList, type PlaygroundEvent } from "@/components/playground-events";
import { Badge, Card, ErrorBox } from "@/components/ui";
import { clientStream, messageOf } from "@/lib/api";
import { formatMoney, formatNumber } from "@/lib/format";

type AgentOption = { id: string; name: string; model: string | null };

export function PlaygroundClient({
  agents,
  canRun,
}: {
  agents: AgentOption[];
  canRun: boolean;
}) {
  const [agentId, setAgentId] = useState(agents[0]?.id ?? "");
  const [input, setInput] = useState("امروز چندم است؟ از ابزار تاریخ استفاده کن.");
  const [text, setText] = useState("");
  const [events, setEvents] = useState<PlaygroundEvent[]>([]);
  const [status, setStatus] = useState("idle");
  const [runId, setRunId] = useState<string | null>(null);
  const [approval, setApproval] = useState<Record<string, unknown> | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function handle(event: string, data: Record<string, unknown>) {
    setEvents((current) => [...current.slice(-120), { event, data }]);
    if (event === "run.started") setRunId(String(data.run_id ?? ""));
    if (event === "token") setText((current) => current + String(data.text ?? ""));
    if (event === "approval.required") {
      setApproval(data);
      setStatus("waiting_approval");
    }
    if (event === "run.waiting_approval") {
      setRunId(String(data.run_id ?? ""));
      setStatus("waiting_approval");
    }
    if (event === "run.completed") {
      setStatus("completed");
      setApproval(null);
      setSummary(
        `گام ${formatNumber(Number(data.steps ?? 0))} · ${formatNumber(
          Number(data.tokens_in ?? 0),
        )}+${formatNumber(Number(data.tokens_out ?? 0))} توکن · ${formatMoney(
          Number(data.cost_irr ?? 0),
        )}`,
      );
    }
    if (event === "run.failed") {
      setStatus("failed");
      setError(String(data.code ?? ""));
    }
  }

  async function start() {
    if (!agentId) {
      setError("ابتدا یک ایجنت انتخاب کنید.");
      return;
    }
    setBusy(true);
    setError(null);
    setText("");
    setEvents([]);
    setApproval(null);
    setSummary(null);
    setStatus("running");
    abortRef.current = new AbortController();
    try {
      await clientStream(
        `/agents/${agentId}/runs`,
        { input, stream: true },
        handle,
        abortRef.current.signal,
      );
    } catch (err) {
      setError(messageOf(err));
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!runId) return;
    setBusy(true);
    setError(null);
    setApproval(null);
    setStatus("running");
    try {
      await clientStream(`/runs/${runId}/approve`, { stream: true }, handle);
    } catch (err) {
      setError(messageOf(err));
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
    setBusy(false);
    setStatus("cancelled");
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-4">
        <Card>
          <div className="card-body space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex-1">
                <span className="label">ایجنت</span>
                <select
                  className="input"
                  value={agentId}
                  onChange={(event) => setAgentId(event.target.value)}
                >
                  {agents.length === 0 ? <option value="">— ایجنتی نیست —</option> : null}
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} {agent.model ? `(${agent.model})` : "(بدون مدل)"}
                    </option>
                  ))}
                </select>
              </label>
              <Badge value={status === "idle" ? "queued" : status} />
            </div>

            <label className="block">
              <span className="label">پیام</span>
              <textarea
                className="input min-h-24 resize-y"
                value={input}
                onChange={(event) => setInput(event.target.value)}
              />
            </label>

            <div className="flex flex-wrap gap-2">
              <button className="btn-primary" onClick={() => void start()} disabled={busy || !canRun}>
                {busy ? "در حال اجرا…" : "ارسال"}
              </button>
              <button className="btn-ghost" onClick={stop} disabled={!busy}>
                توقف
              </button>
            </div>

            {!canRun ? <p className="muted">نقش شما اجازه‌ی اجرا ندارد.</p> : null}
            {error ? <ErrorBox message={error} /> : null}
          </div>
        </Card>

        {approval ? (
          <ApprovalCard
            approval={approval}
            busy={busy}
            onApprove={() => void approve()}
            onDismiss={() => setApproval(null)}
          />
        ) : null}

        <Card>
          <div className="card-body">
            <p className="mb-2 text-sm font-medium text-ink-700">پاسخ ایجنت</p>
            <div className="min-h-24 whitespace-pre-wrap rounded-lg bg-ink-50 p-3 text-sm leading-7">
              {text || <span className="text-ink-400">هنوز پاسخی نیامده است…</span>}
            </div>
            {summary ? <p className="mt-2 text-xs text-ink-500">{summary}</p> : null}
          </div>
        </Card>
      </div>

      <Card className="h-fit">
        <div className="border-b border-ink-100 px-4 py-3 text-sm font-medium text-ink-700">
          رخدادهای اجرا
        </div>
        <EventList events={events} />
      </Card>
    </div>
  );
}
