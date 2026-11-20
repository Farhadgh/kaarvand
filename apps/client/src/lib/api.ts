/** Thin fetch wrapper: base URL, bearer token, one automatic refresh on 401. */

import { clearSession, loadSession, saveSession, type Session, type User } from "./auth";

export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly params: Record<string, unknown>;

  constructor(status: number, code: string, params: Record<string, unknown> = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.params = params;
  }
}

type ErrorEnvelope = { error?: { code?: string; params?: Record<string, unknown> } };

async function toError(response: Response): Promise<ApiError> {
  let code = "common.error";
  let params: Record<string, unknown> = {};
  try {
    const body = (await response.json()) as ErrorEnvelope;
    code = body.error?.code ?? code;
    params = body.error?.params ?? {};
  } catch {
    /* non JSON error body */
  }
  return new ApiError(response.status, code, params);
}

async function refreshSession(): Promise<Session | null> {
  const current = loadSession();
  if (!current) return null;
  const response = await fetch(`${API_BASE}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: current.refreshToken }),
  });
  if (!response.ok) {
    clearSession();
    return null;
  }
  const tokens = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  const next: Session = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    user: current.user,
  };
  saveSession(next);
  return next;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const session = loadSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (session) headers.set("Authorization", `Bearer ${session.accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "common.network");
  }

  if (response.status === 401 && retry && session) {
    const refreshed = await refreshSession();
    if (refreshed) return apiFetch<T>(path, init, false);
  }

  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type OtpRequest = {
  sent: boolean;
  expires_in: number;
  resend_in: number;
  sms_delivered: boolean;
  debug_code: string | null;
};

export type OtpLogin = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  is_new_user: boolean;
  user: User;
};

export type Wallet = {
  balance_irr: number;
  balance_toman: number;
  currency: string;
  is_enabled: boolean;
  usd_irr: number;
  markup_percent: number;
  min_topup_irr: number;
  min_topup_toman: number;
  topup_enabled: boolean;
};

export type Payment = {
  id: string;
  amount_irr: number;
  amount_toman: number;
  status: "pending" | "paid" | "canceled" | "failed";
  gateway: string;
  reference: string | null;
  description_fa: string | null;
  paid_at: string | null;
  created_at: string | null;
};

export type Topup = {
  payment_id: string;
  amount_irr: number;
  amount_toman: number;
  gateway: string;
  authority: string | null;
  redirect_url: string;
  status: string;
};

/** Customer view of a model: Toman prices, no provider identity. */
export type CatalogModel = {
  id: string;
  name: string;
  family: string | null;
  context_window: number | null;
  max_output: number | null;
  modalities: string[];
  capabilities: string[];
  audio_kind: "stt" | "tts" | null;
  audio_chat: boolean;
  persian: string | null;
  billing_unit: "per_1m_tokens" | "per_minute" | "per_1k_chars";
  price_input_toman: number | null;
  price_output_toman: number | null;
  price_image_toman: number | null;
  price_audio_minute_toman: number | null;
  price_audio_1k_chars_toman: number | null;
  price_known: boolean;
};

/** A customer's own assistant (the API hides other people's agents). */
export type Agent = {
  id: string;
  name: string;
  role: string;
  created_by: string | null;
  system_prompt_key: string;
  model_id: string | null;
  model_external_id: string | null;
  model_display_name_fa: string | null;
  temperature: string | number;
  max_tokens: number;
  memory_mode: string;
  monthly_budget_irr: number | null;
  is_active: boolean;
};

export type RunStatus = "queued" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";

export type RunSummary = {
  id: string;
  agent_id: string | null;
  created_by: string | null;
  status: RunStatus;
  trigger: string;
  steps_taken: number;
  tokens_in: number;
  tokens_out: number;
  /** what the customer paid, in Rial (divide by 10 for Toman) */
  cost_irr: number;
  error_code: string | null;
  created_at: string | null;
};

export type RunResult = { run: RunSummary; text: string };

/** A messenger/webhook connection bound to one agent. */
export type Channel = {
  id: string;
  slug: string;
  name_fa: string;
  provider: "telegram" | "whatsapp";
  agent_id: string;
  reply_mode: "off" | "auto";
  is_active: boolean;
  events_count: number;
  last_event_at: string | null;
  has_secret: boolean;
  webhook_url: string;
  last_event_status: string | null;
};

export const api = {
  requestOtp: (phone: string) =>
    apiFetch<OtpRequest>("/v1/auth/otp/request", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  verifyOtp: (phone: string, code: string) =>
    apiFetch<OtpLogin>("/v1/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code }),
    }),

  me: () => apiFetch<User>("/v1/auth/me"),

  wallet: () => apiFetch<Wallet>("/v1/wallet"),

  payments: () => apiFetch<Payment[]>("/v1/wallet/payments"),

  catalog: (params: { capability?: string; q?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.capability) search.set("capability", params.capability);
    if (params.q) search.set("q", params.q);
    const query = search.toString();
    return apiFetch<CatalogModel[]>(`/v1/catalog/models${query ? `?${query}` : ""}`);
  },

  topup: (amountToman: number) =>
    apiFetch<Topup>("/v1/wallet/topup", {
      method: "POST",
      body: JSON.stringify({ amount_toman: amountToman }),
    }),

  logout: (refreshToken: string) =>
    apiFetch<{ ok: boolean }>("/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  agents: () => apiFetch<Agent[]>("/v1/agents"),

  createAgent: (body: { name: string; model_id?: string | null; role?: string }) =>
    apiFetch<Agent>("/v1/agents", { method: "POST", body: JSON.stringify(body) }),

  updateAgent: (id: string, body: { is_active?: boolean; name?: string }) =>
    apiFetch<Agent>(`/v1/agents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  deleteAgent: (id: string) => apiFetch<void>(`/v1/agents/${id}`, { method: "DELETE" }),

  runs: (limit = 50) => apiFetch<RunSummary[]>(`/v1/runs?limit=${limit}`),

  startRun: (agentId: string, input: string) =>
    apiFetch<RunResult>(`/v1/agents/${agentId}/runs`, {
      method: "POST",
      body: JSON.stringify({ input, stream: false }),
    }),

  channels: () => apiFetch<Channel[]>("/v1/channels"),

  createChannel: (body: {
    name_fa: string;
    provider: "telegram" | "whatsapp";
    agent_id: string;
    reply_mode?: "off" | "auto";
  }) => apiFetch<Channel>("/v1/channels", { method: "POST", body: JSON.stringify(body) }),

  deleteChannel: (id: string) => apiFetch<void>(`/v1/channels/${id}`, { method: "DELETE" }),
};

