/**
 * Bridge to the Electron shell. In a plain browser (and inside the Capacitor
 * WebView) `window.kaarvand` does not exist, so every helper degrades to the
 * standard web behaviour.
 */

export type DesktopBridge = {
  platform: string;
  electron?: string;
  openExternal: (url: string) => Promise<boolean>;
  onDeepLink: (callback: (url: string) => void) => () => void;
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
