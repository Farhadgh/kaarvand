/**
 * The device side of the browser bridge.
 *
 * This laptop has to be reachable by the server *without* an open port, so it
 * dials out: pair once (a code from the panel), keep the device token, then hold
 * a websocket and answer `link.command` / `script.run` frames. The Chromium
 * profiles themselves live in the Electron main process (see `electron/bridge.cjs`).
 */

import { api } from "./api";
import { desktop, type DeviceBridge, type StoredDevice } from "./desktop";

const LOCAL_KEY = "kaarvand.device";

/** Ops this device can execute; the panel shows them next to the device. */
export const BRIDGE_OPS = [
  "browser.goto",
  "browser.wait_for",
  "browser.click",
  "browser.type",
  "browser.press",
  "browser.extract",
  "browser.wait",
  "screenshot",
];

export type DeviceMessage = Record<string, unknown>;

function osName(): string {
  const platform = desktop()?.platform ?? "";
  if (platform.startsWith("win")) return "Windows";
  if (platform === "darwin") return "macOS";
  if (platform === "linux") return "Linux";
  return "Web";
}

export async function loadDevice(): Promise<StoredDevice | null> {
  const store = desktop()?.device;
  if (store) return store.get();
  try {
    const raw = localStorage.getItem(LOCAL_KEY);
    return raw ? (JSON.parse(raw) as StoredDevice) : null;
  } catch {
    return null;
  }
}

export async function saveDevice(device: StoredDevice | null): Promise<void> {
  const store = desktop()?.device;
  if (store) {
    await store.set(device);
    return;
  }
  if (device) localStorage.setItem(LOCAL_KEY, JSON.stringify(device));
  else localStorage.removeItem(LOCAL_KEY);
}

/**
 * The device token for *this* machine, pairing on first use.
 *
 * A token that the server no longer knows (device deleted, database restored)
 * is detected with one cheap list call and replaced, so a stale file can never
 * leave the bridge silently offline.
 */
export async function ensureDevice(): Promise<StoredDevice> {
  const stored = await loadDevice();
  if (stored) {
    const rows = await api.devices().catch(() => []);
    if (rows.some((row) => row.id === stored.deviceId)) return stored;
  }

  const created = await api.createDevice(osName() === "Web" ? "مرورگر من" : "این دستگاه");
  if (!created.pairing_code) throw new Error("device.pairing_unavailable");
  const paired = await api.pairDevice(created.pairing_code, osName());
  const device: StoredDevice = {
    deviceId: paired.device_id,
    token: paired.device_token,
    wsUrl: paired.ws_url,
  };
  await saveDevice(device);
  return device;
}

type Reply = (payload: DeviceMessage) => void;

/** One server frame -> one bridge call -> one result frame. */
export async function handleDeviceMessage(
  message: DeviceMessage,
  reply: Reply,
  bridge: DeviceBridge | undefined,
): Promise<void> {
  const kind = String(message.type ?? "");
  const callId = message.call_id;

  const fail = (error: string) =>
    reply({
      type: kind === "script.run" ? "script.result" : "link.result",
      call_id: callId,
      ok: false,
      error,
    });

  if (!bridge) {
    fail("bridge_unavailable");
    return;
  }

  if (kind === "link.command") {
    const provider = String(message.provider ?? "");
    const siteUrl = String(message.site_url ?? "");
    const action = String(message.action ?? "");
    let result;
    if (action === "open") result = await bridge.open(provider, siteUrl);
    else if (action === "probe")
      result = await bridge.probe(provider, {
        siteUrl,
        loginCheck: (message.login_check as Record<string, unknown>) ?? {},
      });
    else if (action === "wipe") result = await bridge.wipe(provider);
    else if (action === "stop") result = await bridge.stop(provider);
    else result = { ok: false, error: "unknown_action" };
    reply({ type: "link.result", call_id: callId, ...result });
    return;
  }

  if (kind === "script.run") {
    const slug = String(message.tool ?? "");
    // the tool slug carries the provider: facebook.<link8>.post
    const provider = slug.split(".")[0];
    const steps = Array.isArray(message.steps) ? (message.steps as Record<string, unknown>[]) : [];
    const goto = steps.find((step) => step.op === "browser.goto" || step.op === "browser.open");
    const result = await bridge.run(provider, steps, {
      siteUrl: goto ? String(goto.url ?? "") : undefined,
    });
    reply({
      type: "script.result",
      call_id: callId,
      ok: result.ok,
      error: result.error,
      output: result.output,
      artifacts: result.artifacts,
    });
    return;
  }

  // anything else is not ours (hello.ack, pong, progress)
}

/** Long lived websocket with backoff; survives sleep/wake and server restarts. */
export class DeviceConnector {
  private socket: WebSocket | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private attempts = 0;
  private closed = false;

  constructor(
    private readonly device: StoredDevice,
    private readonly bridge: DeviceBridge | undefined,
  ) {}

  start(): void {
    this.connect();
  }

  stop(): void {
    this.closed = true;
    if (this.retry) clearTimeout(this.retry);
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.socket?.close();
  }

  private connect(): void {
    if (this.closed) return;
    const separator = this.device.wsUrl.includes("?") ? "&" : "?";
    const url = `${this.device.wsUrl}${separator}token=${encodeURIComponent(this.device.token)}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.attempts = 0;
      socket.send(
        JSON.stringify({
          type: "hello",
          name: "کاروند دسکتاپ",
          os: osName(),
          version: "0.1.0",
          manifest: { ops: BRIDGE_OPS },
        }),
      );
      this.heartbeat = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" }));
      }, 25000);
    };

    socket.onmessage = (event) => {
      let message: DeviceMessage;
      try {
        message = JSON.parse(String(event.data)) as DeviceMessage;
      } catch {
        return;
      }
      if (message.type === "hello.ack" || message.type === "pong") return;
      void handleDeviceMessage(
        message,
        (payload) => {
          if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload));
        },
        this.bridge,
      );
    };

    socket.onclose = () => {
      if (this.heartbeat) clearInterval(this.heartbeat);
      this.heartbeat = null;
      this.schedule();
    };
    socket.onerror = () => {
      try {
        socket.close();
      } catch {
        /* already closed */
      }
    };
  }

  private schedule(): void {
    if (this.closed) return;
    this.attempts += 1;
    const wait = Math.min(5000 * this.attempts, 60000);
    this.retry = setTimeout(() => this.connect(), wait);
  }
}

/**
 * One connector per window.
 *
 * ``RequireAuth`` is mounted per route, so a naive effect would drop and redial
 * the websocket on every navigation. The device connection belongs to the app
 * lifetime, not to a page.
 */
let shared: DeviceConnector | null = null;
let starting = false;

export function sharedConnector(
  device: StoredDevice,
  bridge: DeviceBridge | undefined,
): DeviceConnector | null {
  if (shared) return shared;
  if (starting) return null;
  starting = true;
  shared = new DeviceConnector(device, bridge);
  shared.start();
  starting = false;
  return shared;
}

export function stopSharedConnector(): void {
  shared?.stop();
  shared = null;
}

