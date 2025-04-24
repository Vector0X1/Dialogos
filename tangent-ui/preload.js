// preload.js
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // Expose protected methods here
});