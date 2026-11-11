/** Runtime types: tools, devices, runs, usage, settings. */

export type ToolKind = "builtin" | "http" | "mcp" | "connector";

export interface Tool {
  id: string;
  org_id: string | null;
  slug: string;
  name_fa: string;
  description_fa: string | null;
  kind: ToolKind;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  config: Record<string, unknown>;
  actions: Record<string, unknown>[];
  risk_level: "low" | "medium" | "high";
  approval_policy: "auto" | "confirm" | "deny";
  category: string;
  is_enabled: boolean;
  has_secret: boolean;
  secret_masked: string | null;
  secret_label: string | null;
}

export interface LlmTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  slug: string;
}

export interface AppCredential {
  key: string;
  label_fa: string;
  secret?: boolean;
  required?: boolean;
  placeholder?: string;
}

export interface CatalogApp {
  id: string;
  slug: string;
  name_fa: string;
  name_en: string | null;
  vendor: string | null;
  description_fa: string | null;
  icon: string;
  color: string | null;
  category: string;
  runtime: string;
  tool_kind: string;
  risk_level: string;
  approval_policy: string;
  requires_device: boolean;
  setup_fa: string | null;
  docs_url: string | null;
  sort_order: number;
  installed_tools: number;
  installed_agents: number;
  detected_devices: number;
}

export interface CatalogAppDetail extends CatalogApp {
  input_schema: Record<string, unknown>;
  config_template: Record<string, unknown>;
  actions_template: Record<string, unknown>[];
  credentials: AppCredential[];
  detect: Record<string, unknown>;
}

export interface AppInstallResult {
  tool_id: string;
  slug: string;
  agent_id: string;
  permission_level: string;
  device_id: string | null;
  warnings: string[];
}

export interface InboundChannel {
  id: string;
  slug: string;
  name_fa: string;
  provider: string;
  agent_id: string;
  tool_id: string | null;
  reply_mode: string;
  is_active: boolean;
  last_event_at: string | null;
  events_count: number;
  has_secret: boolean;
  has_verify_token: boolean;
  webhook_path: string;
  verify_path: string;
  webhook_url: string;
  last_event_status: string | null;
  last_reply_status: string | null;
  last_error: string | null;
}

export interface InboundTestResult {
  ok: boolean;
  status: string;
  run_id: string | null;
  run_status: string | null;
  reply_status: string | null;
  needs_approval: boolean;
  text: string | null;
}

export interface WebhookRegisterResult {
  ok: boolean;
  url: string;
  detail: string | null;
  public_base_url: boolean;
}

export interface InboundEvent {
  id: string;
  channel_id: string;
  provider: string;
  external_id: string;
  status: string;
  run_id: string | null;
  from_id: string | null;
  chat_id: string | null;
  text: string | null;
  reply_status: string | null;
  error: string | null;
  created_at: string | null;
}

export interface DeviceApp {
  app_slug: string;
  name_fa: string | null;
  icon: string | null;
  color: string | null;
  version: string | null;
  exe: string | null;
  prog_id: string | null;
  is_granted: boolean;
  detected_at: string | null;
  in_catalog: boolean;
}

export interface ActionOp {
  op: string;
  title_fa: string;
  required: string[];
}

export interface Device {
  id: string;
  name: string;
  os: string | null;
  version: string | null;
  status: string;
  allowed_paths: string[];
  is_active: boolean;
  last_seen_at: string | null;
}

export interface DeviceWithCode extends Device {
  pairing_code: string;
  pairing_expires_at: string;
}

export interface DeviceOps {
  device_id: string;
  online: boolean;
  ops: string[];
  manifest: Record<string, unknown>;
}

export interface Run {
  id: string;
  agent_id: string | null;
  conversation_id: string | null;
  status: string;
  trigger: string;
  steps_taken: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: string;
  cost_irr: number;
  fx_rate: string | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RunResult {
  run: Run;
  text: string;
  events: RunEvent[];
}

export interface RunEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface ToolInvocation {
  id: string;
  tool_slug: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
  status: string;
  risk_level: string;
  latency_ms: number | null;
  approved_by: string | null;
  created_at: string;
}

export interface UsageBucket {
  key: string;
  label: string;
  runs: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: string;
  cost_irr: number;
}

export interface UsageSummary {
  days: number;
  fx_rate: number;
  range_from: string;
  range_to: string;
  totals: {
    runs: number;
    tokens_in: number;
    tokens_out: number;
    cost_usd: string;
    cost_irr: number;
  };
  by_day: UsageBucket[];
  by_agent: UsageBucket[];
  by_model: UsageBucket[];
  runs: { running: number; waiting_approval: number; failed: number; completed: number };
  agents_total: number;
  agents_active: number;
  devices_total: number;
  devices_online: number;
  pending_approvals: number;
  budget: { org_monthly_irr: number | null; org_spent_irr: number };
}

export interface SettingsPayload {
  org: {
    id: string;
    name: string;
    slug: string;
    timezone: string;
    calendar: string;
    currency: string;
    digits: string;
    tax_rate: string;
    invoice_prefix: string;
    monthly_budget_irr: number | null;
  };
  me: {
    id: string;
    email: string;
    full_name: string;
    role: string;
    locale: string;
    digits_pref: "fa" | "en";
  };
  fx: { usd_irr: number; source: string };
  free_mode: boolean;
  billing_enabled: boolean;
  payment_gateway: string;
  version: string;
  locale: string;
  calendar: string;
  digits: string;
  timezone: string;
}
