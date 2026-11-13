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
});
