"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, Card, CardHeader, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { categoryLabels, messages, permissionLabels, toolKindLabels } from "@/lib/copy";
import type { Tool } from "@/lib/types";

export function ToolsClient({ tools, canEdit }: { tools: Tool[]; canEdit: boolean }) {
  const router = useRouter();
  const [openId, setOpenId] = useState<string | null>(null);
  const [args, setArgs] = useState("{}");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const filtered = tools.filter((tool) => {
    if (!filter) return true;
    return (
      tool.kind === filter ||
      tool.category === filter ||
      tool.slug.includes(filter) ||
      tool.name_fa.includes(filter)
    );
  });

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

  async function test(tool: Tool) {
    setBusy(`test-${tool.id}`);
    setError(null);
    setResult(null);
    try {
      const response = await clientFetch<{ ok: boolean; result: Record<string, unknown> }>(
        `/tools/${tool.id}/test`,
        { method: "POST", body: JSON.stringify({ arguments: JSON.parse(args || "{}") }) },
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <ErrorBox message={error} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        {["", "builtin", "http", "mcp", "connector"].map((value) => (
          <button
            key={value || "all"}
            className={`btn-ghost !px-3 !py-1.5 text-xs ${
              filter === value ? "!border-brand-400 !text-brand-700" : ""
            }`}
            onClick={() => setFilter(value)}
          >
            {value ? toolKindLabels[value] : "همه"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {filtered.map((tool) => (
          <Card key={tool.id}>
            <CardHeader
              title={tool.name_fa}
              subtitle={`${tool.slug} · ${toolKindLabels[tool.kind] ?? tool.kind}`}
              action={
                <div className="flex items-center gap-1">
                  <Badge value={tool.risk_level} />
                  <Badge value="queued" label={permissionLabels[tool.approval_policy]} />
                </div>
              }
            />
            <div className="card-body space-y-3">
              <p className="text-sm text-ink-600">{tool.description_fa ?? "—"}</p>

              <div className="flex flex-wrap items-center gap-2 text-xs text-ink-500">
                <span>{categoryLabels[tool.category] ?? tool.category}</span>
                {tool.has_secret ? <span>· اعتبارنامه ثبت‌شده</span> : null}
                {tool.org_id === null ? <span>· سراسری</span> : null}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-ghost !px-2 !py-1 text-xs"
                  onClick={() => {
                    setOpenId(openId === tool.id ? null : tool.id);
                    setResult(null);
                  }}
                >
                  تست ابزار
                </button>
                <button
                  className="btn-ghost !px-2 !py-1 text-xs"
                  disabled={!canEdit || busy === tool.id}
                  onClick={() =>
                    void act(tool.id, () =>
                      clientFetch(`/tools/${tool.id}`, {
                        method: "PATCH",
                        body: JSON.stringify({ is_enabled: !tool.is_enabled }),
                      }),
                    )
                  }
                >
                  {tool.is_enabled ? "فعال" : "غیرفعال"}
                </button>
                {tool.org_id === null && canEdit ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs"
                    disabled={busy === `clone-${tool.id}`}
                    title="ابزار سراسری قابل ویرایش نیست؛ یک کپی سازمانی بسازید"
                    onClick={() =>
                      void act(`clone-${tool.id}`, () =>
                        clientFetch(`/tools/${tool.id}/clone`, { method: "POST" }),
                      )
                    }
                  >
                    {busy === `clone-${tool.id}` ? "…" : "کپی قابل ویرایش"}
                  </button>
                ) : null}
                {tool.org_id !== null && canEdit ? (
                  <button
                    className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
                    onClick={() => {
                      if (!window.confirm(messages.confirmDelete)) return;
                      void act(`del-${tool.id}`, () =>
                        clientFetch(`/tools/${tool.id}`, { method: "DELETE" }),
                      );
                    }}
                  >
                    حذف
                  </button>
                ) : null}
              </div>

              {openId === tool.id ? (
                <div className="space-y-2 rounded-lg bg-ink-50 p-3">
                  <textarea
                    className="input ltr min-h-24 font-mono text-xs"
                    dir="ltr"
                    value={args}
                    onChange={(event) => setArgs(event.target.value)}
                  />
                  <button
                    className="btn-primary !py-1 text-xs"
                    disabled={busy === `test-${tool.id}`}
                    onClick={() => void test(tool)}
                  >
                    {busy === `test-${tool.id}` ? "در حال اجرا…" : "اجرا"}
                  </button>
                  {result ? (
                    <pre className="ltr max-h-56 overflow-auto rounded bg-white p-2 text-xs">
                      {result}
                    </pre>
                  ) : null}
                </div>
              ) : null}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
