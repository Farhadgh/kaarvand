/**
 * Bridge to the Electron shell. In a plain browser (and inside the Capacitor
 * WebView) `window.kaarvand` does not exist, so every helper degrades to the
 * standard web behaviour.
 */

export type BridgeResult<T = Record<string, unknown>> = { ok: boolean; error?: string } & T;

export type BridgeSite = { provider: string; paused: boolean; url: string | null };

export type DeviceBridge = {
  open: (provider: string, siteUrl: string) => Promise<BridgeResult>;
  probe: (
    provider: string,
    options: { siteUrl?: string; loginCheck?: Record<string, unknown>; screenshot?: boolean },
  ) => Promise<
    BridgeResult<{
      logged_in?: boolean;
      display_name?: string | null;
      url?: string;
      detail?: string | null;
      screenshot?: string | null;
    }>
  >;
  run: (
    provider: string,
    steps: Record<string, unknown>[],
    options?: { siteUrl?: string; visible?: boolean; timeoutMs?: number },
  ) => Promise<BridgeResult<{ output?: unknown[]; artifacts?: string[] }>>;
  wipe: (provider: string) => Promise<BridgeResult>;
  stop: (provider: string) => Promise<BridgeResult>;
  status: () => Promise<BridgeResult<{ sites?: BridgeSite[] }>>;
};

export type StoredDevice = { deviceId: string; token: string; wsUrl: string };

export type DesktopBridge = {
  platform: string;
  electron?: string;
  openExternal: (url: string) => Promise<boolean>;
  onDeepLink: (callback: (url: string) => void) => () => void;
  bridge?: DeviceBridge;
  device?: {
    get: () => Promise<StoredDevice | null>;
    set: (value: StoredDevice | null) => Promise<boolean>;
  };
};

declare global {
  interface Window {
    kaarvand?: DesktopBridge;
  }
}

export function desktop(): DesktopBridge | undefined {
  return typeof window === "undefined" ? undefined : window.kaarvand;
}

/** Open the payment page: system browser on desktop, same tab on the web. */
export async function openExternal(url: string): Promise<void> {
  const bridge = desktop();
  if (bridge) {
    await bridge.openExternal(url);
    return;
  }
  window.location.assign(url);
}

/** `kaarvand://wallet?status=paid&...` -> the path and its query. */
export function parseDeepLink(url: string): { path: string; params: URLSearchParams } {
  const normalized = url.replace(/^kaarvand:\/\//, "https://kaarvand.local/");
  try {
    const parsed = new URL(normalized);
    return { path: parsed.pathname.replace(/^\/+/, "/") || "/", params: parsed.searchParams };
  } catch {
    return { path: "/", params: new URLSearchParams() };
  }
}
