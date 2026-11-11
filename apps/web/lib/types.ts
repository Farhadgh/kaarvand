/** Shared API types (mirror of the FastAPI schemas). */

export type Role = "owner" | "admin" | "operator" | "viewer";

export interface ApiError {
  error: { code: string; params?: Record<string, unknown> };
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  role: Role;
  is_active: boolean;
  locale: string;
  digits_pref: "fa" | "en";
  last_login_at?: string | null;
  created_at?: string | null;
}

export interface Meta {
  app_name: string;
  version: string;
  env: string;
  locale: string;
  timezone: string;
  calendar: string;
  currency: string;
  digits: string;
  free_mode: boolean;
  billing_enabled: boolean;
  payment_gateway: string;
  payment_gateway_enabled: boolean;
  fx_usd_irr: number;
  api_prefix: string;
}

export interface Provider {
  id: string;
  name: string;
  slug: string;
  kind: string;
  base_url: string | null;
  auth_type: string;
  extra_headers: Record<string, string>;
  models_url: string | null;
  prices_url: string | null;
  priority: number;
  is_enabled: boolean;
  health: string;
  health_message: string | null;
  has_credentials: boolean;
  api_key_masked: string | null;
  last_synced_at: string | null;
}

export interface ProviderAdapter {
  kind: string;
  title_fa: string;
  description_fa: string | null;
  is_builtin: boolean;
  spec_schema: Record<string, unknown>;
}

export interface Model {
  id: string;
  provider_id: string;
  external_id: string;
  display_name_fa: string | null;
  family: string | null;
  context_window: number | null;
  max_output: number | null;
  modalities: string[];
  supports_tools: boolean;
  supports_stream: boolean;
  supports_vision: boolean;
  supports_audio: boolean;
  supports_reasoning: boolean;
  input_price: string | null;
  output_price: string | null;
  cached_input_price: string | null;
  image_price: string | null;
  price_currency: string;
  price_source: string | null;
  price_synced_at: string | null;
  markup_percent: string;
  is_enabled: boolean;
}

export interface Prompt {
  id: string;
  org_id: string | null;
  key: string;
  locale: string;
  kind: string;
  title_fa: string;
  template: string;
  variables: string[];
  status: string;
  current_version: number;
  updated_at: string;
}

export interface PromptVersion {
  id: string;
  version: number;
  template: string;
  variables: string[];
  note: string | null;
  created_at: string;
}

export interface RenderedPrompt {
  key: string;
  version: number;
  template: string;
  rendered: string;
  variables: string[];
  missing: string[];
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  avatar_url: string | null;
  system_prompt_key: string;
  model_id: string | null;
  model_external_id: string | null;
  model_display_name_fa: string | null;
  temperature: string;
  max_tokens: number;
  memory_mode: string;
  guardrails: Record<string, unknown>;
  monthly_budget_irr: number | null;
  is_active: boolean;
}

export interface AgentTask {
  id: string;
  agent_id: string;
  name: string;
  prompt_key: string | null;
  prompt_template: string | null;
  inputs_schema: Record<string, unknown>;
  steps: Record<string, unknown>[];
  schedule_cron: string | null;
  trigger_type: string;
  requires_approval: boolean;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export * from "./types-more";
