import { useEffect } from "react";

import { loadSession } from "../lib/auth";
import { desktop } from "../lib/desktop";
import { ensureDevice, sharedConnector, stopSharedConnector } from "../lib/device";

/**
 * Keeps this device connected while the app is open.
 *
 * Mounted inside ``RequireAuth`` so it starts after login; the websocket is the
 * only way the server can reach the customer's browser profiles (no open port,
 * no static IP). The connector itself is a window level singleton, so route
 * changes never redial it.
 */
export default function DeviceBridge() {
  useEffect(() => {
    if (!loadSession()) {
      stopSharedConnector();
      return;
    }
    const bridge = desktop()?.bridge;
    let cancelled = false;

    void (async () => {
      try {
        const device = await ensureDevice();
        if (cancelled) return;
        sharedConnector(device, bridge);
      } catch {
        // offline or not paired yet: the next mount (or the Accounts page) retries
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
