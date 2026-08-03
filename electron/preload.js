const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rpgrtl', {
  backendPort: () => ipcRenderer.invoke('backend:getPort'),
  selectProject: () => ipcRenderer.invoke('dialog:selectProject'),
  selectGameFolder: () => ipcRenderer.invoke('dialog:selectGameFolder'),
  openPack: (payload) => ipcRenderer.invoke('dialog:openPack', payload),
  savePack: (payload) => ipcRenderer.invoke('dialog:savePack', payload),
  openPath: (targetPath) => ipcRenderer.invoke('shell:openPath', targetPath),
  openExternal: (targetUrl) => ipcRenderer.invoke('shell:openExternal', targetUrl),
  appVersion: () => ipcRenderer.invoke('app:getVersion'),
  startAccountLogin: (payload) => ipcRenderer.invoke('account:login', payload),
  getAccountStatus: (payload) => ipcRenderer.invoke('account:status', payload),
  checkUpdate: () => ipcRenderer.invoke('update:check')
});
