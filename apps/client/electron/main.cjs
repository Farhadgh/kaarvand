// Electron main process: one window, kaarvand:// deep links, external links
// opened in the system browser (the Zarinpal return flow relies on this).
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("node:path");

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
