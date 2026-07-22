const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rpgrtl', {
  backendPort: () => ipcRenderer.invoke('backend:getPort'),
  selectProject: () => ipcRenderer.invoke('dialog:selectProject'),
  selectGameFolder: () => ipcRenderer.invoke('dialog:selectGameFolder'),
  openPack: () => ipcRenderer.invoke('dialog:openPack'),
  savePack: () => ipcRenderer.invoke('dialog:savePack'),
  openPath: (targetPath) => ipcRenderer.invoke('shell:openPath', targetPath),
  openExternal: (targetUrl) => ipcRenderer.invoke('shell:openExternal', targetUrl),
  appVersion: () => ipcRenderer.invoke('app:getVersion'),
  checkUpdate: () => ipcRenderer.invoke('update:check')
});
