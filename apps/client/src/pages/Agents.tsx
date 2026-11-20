import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError, type Agent } from "../lib/api";
import { faError } from "../lib/errors-fa";
import { faDigits } from "../lib/money";

/** Create and manage your own assistants; each one is bound to one model. */
export default function Agents() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [modelId, setModelId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents });
  const models = useQuery({ queryKey: ["catalog", "", ""], queryFn: () => api.catalog() });

  // audio models are billed per minute/character and cannot drive a chat agent
  const chatModels = (models.data ?? []).filter((item) => item.billing_unit === "per_1m_tokens");

  function fail(err: unknown) {
    setError(faError((err as ApiError).code));
  }

  const create = useMutation({
    mutationFn: () => api.createAgent({ name: name.trim(), model_id: modelId || null }),
    onSuccess: async () => {
      setName("");
      setModelId("");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: fail,
  });

  const toggle = useMutation({
    mutationFn: (agent: Agent) => api.updateAgent(agent.id, { is_active: !agent.is_active }),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: fail,
  });

  const remove = useMutation({
    mutationFn: (agent: Agent) => api.deleteAgent(agent.id),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: fail,
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-5 pb-16">
      <header className="flex items-center justify-between">
        <button className="btn-ghost text-xs" onClick={() => navigate("/")}>
          بازگشت
        </button>
        <h1 className="text-lg font-bold">ایجنت‌های من</h1>
      </header>

      <section className="card space-y-3">
        <p className="text-sm font-semibold">ایجنت تازه</p>

        <input
          className="input"
          placeholder="نام ایجنت (مثلاً دستیار فروش)"
          value={name}
          maxLength={160}
          onChange={(event) => setName(event.target.value)}
        />

        <select
          className="input"
          value={modelId}
          onChange={(event) => setModelId(event.target.value)}
        >
          <option value="">مدل پیش‌فرض سامانه</option>
          {chatModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name}
            </option>
          ))}
        </select>

        <button
          className="btn-primary w-full"
          disabled={create.isPending || name.trim().length === 0}
          onClick={() => create.mutate()}
        >
          {create.isPending ? "در حال ساخت…" : "ساخت ایجنت"}
        </button>

        {error ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>
        ) : null}
      </section>

      <section className="space-y-2">
        <p className="text-sm font-semibold">ایجنت‌ها</p>

        {agents.isLoading ? (
          <p className="text-xs text-slate-400">در حال بارگذاری…</p>
        ) : agents.isError ? (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
            فهرست ایجنت‌ها دریافت نشد. اتصال خود را بررسی کنید.
          </p>
        ) : (agents.data ?? []).length === 0 ? (
          <p className="text-xs text-slate-400">
            هنوز ایجنتی نساخته‌اید؛ از فرم بالا شروع کنید.
          </p>
        ) : (
          (agents.data ?? []).map((agent) => (
            <article key={agent.id} className="card space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">{agent.name}</p>
                  <p className="text-xs text-slate-400">
                    {agent.model_display_name_fa ?? "مدل پیش‌فرض"}
                    {agent.monthly_budget_irr
                      ? ` · سقف ماهانه ${faDigits(
                          Math.round(agent.monthly_budget_irr / 10).toLocaleString("en-US"),
                        )} تومان`
                      : ""}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-1 text-[11px] ${
                    agent.is_active
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {agent.is_active ? "فعال" : "غیرفعال"}
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-primary px-3 py-1.5 text-xs"
                  disabled={!agent.is_active}
                  onClick={() => navigate(`/runs?agent=${agent.id}`)}
                >
                  گفتگو
                </button>
                <button
                  className="btn-ghost px-3 py-1.5 text-xs"
                  disabled={toggle.isPending}
                  onClick={() => toggle.mutate(agent)}
                >
                  {agent.is_active ? "غیرفعال کن" : "فعال کن"}
                </button>
                <button
                  className="btn-ghost px-3 py-1.5 text-xs text-rose-700"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (window.confirm(`ایجنت «${agent.name}» حذف شود؟`)) remove.mutate(agent);
                  }}
                >
                  حذف
                </button>
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
