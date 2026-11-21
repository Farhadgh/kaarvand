// Electron main process: one window, kaarvand:// deep links, external links
// opened in the system browser (the Zarinpal return flow relies on this), and
// the browser bridge that holds the customer's logged in site profiles.
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const bridge = require("./bridge.cjs");

const PROTOCOL = "kaarvand";
const devServerUrl = process.env.VITE_DEV_SERVER_URL;

app.setAsDefaultProtocolClient(PROTOCOL);

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 420,
    minHeight: 640,
    backgroundColor: "#f8fafc",
    title: "کاروند",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  if (devServerUrl) {
    void win.loadURL(devServerUrl);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    void win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

function focusWindow() {
  const win = BrowserWindow.getAllWindows()[0];
  if (win) {
    if (win.isMinimized()) win.restore();
    win.focus();
  }
}

function dispatchDeepLink(argv) {
  const url = argv.find((arg) => typeof arg === "string" && arg.startsWith(`${PROTOCOL}://`));
  if (!url) return;
  const win = BrowserWindow.getAllWindows()[0];
  if (win) win.webContents.send("kaarvand:deep-link", url);
}

ipcMain.handle("kaarvand:open-external", async (_event, url) => {
  if (typeof url === "string" && /^https?:\/\//.test(url)) {
    await shell.openExternal(url);
    return true;
  }
  return false;
});

// --- browser bridge -------------------------------------------------------
// The renderer keeps the websocket (it owns the session and the API base); the
// main process owns the Chromium profiles. Every call is wrapped so a failing
// page can never crash the app.
function deviceFile() {
  return path.join(app.getPath("userData"), "device.json");
}

function wrap(handler) {
  return async (_event, ...args) => {
    try {
      return { ok: true, ...(await handler(...args)) };
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : String(error),
        step: error && typeof error === "object" ? error.step : undefined,
        op: error && typeof error === "object" ? error.op : undefined,
        output: error && typeof error === "object" ? error.output : undefined,
        artifacts: error && typeof error === "object" ? error.artifacts : undefined,
      };
    }
  };
}

ipcMain.handle(
  "bridge:open",
  wrap(async (provider, siteUrl) => bridge.openSite(String(provider), String(siteUrl))),
);

ipcMain.handle(
  "bridge:probe",
  wrap(async (provider, options) => bridge.probe(String(provider), options || {})),
);

ipcMain.handle(
  "bridge:run",
  wrap(async (provider, steps, options) =>
    bridge.runSteps(String(provider), steps, options || {}),
  ),
);

ipcMain.handle("bridge:wipe", wrap(async (provider) => bridge.wipe(String(provider))));
ipcMain.handle("bridge:stop", wrap(async (provider) => bridge.stop(String(provider))));
ipcMain.handle("bridge:status", wrap(async () => ({ sites: bridge.status() })));

ipcMain.handle("device:get", async () => {
  try {
    return JSON.parse(fs.readFileSync(deviceFile(), "utf8"));
  } catch {
    return null;
  }
});

ipcMain.handle("device:set", async (_event, value) => {
  try {
    if (value) fs.writeFileSync(deviceFile(), JSON.stringify(value), { mode: 0o600 });
    else fs.rmSync(deviceFile(), { force: true });
    return true;
  } catch {
    return false;
  }
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    focusWindow();
    dispatchDeepLink(argv);
  });

  app.whenReady().then(() => {
    createWindow();
    dispatchDeepLink(process.argv);

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
