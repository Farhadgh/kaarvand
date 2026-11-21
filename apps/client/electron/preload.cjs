// Only a tiny, explicit surface reaches the renderer.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("kaarvand", {
  platform: process.platform,
  electron: process.versions.electron,
  openExternal: (url) => ipcRenderer.invoke("kaarvand:open-external", url),
  onDeepLink: (callback) => {
    const handler = (_event, url) => callback(url);
    ipcRenderer.on("kaarvand:deep-link", handler);
    return () => ipcRenderer.removeListener("kaarvand:deep-link", handler);
  },
  // browser bridge: the profiles live in the main process, the commands come
  // from the device websocket in the renderer
  bridge: {
    open: (provider, siteUrl) => ipcRenderer.invoke("bridge:open", provider, siteUrl),
    probe: (provider, options) => ipcRenderer.invoke("bridge:probe", provider, options),
    run: (provider, steps, options) =>
      ipcRenderer.invoke("bridge:run", provider, steps, options),
    wipe: (provider) => ipcRenderer.invoke("bridge:wipe", provider),
    stop: (provider) => ipcRenderer.invoke("bridge:stop", provider),
    status: () => ipcRenderer.invoke("bridge:status"),
  },
  device: {
    get: () => ipcRenderer.invoke("device:get"),
    set: (value) => ipcRenderer.invoke("device:set", value),
  },
});
