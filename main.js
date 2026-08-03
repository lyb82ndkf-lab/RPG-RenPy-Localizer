const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');
const { spawn } = require('child_process');

let mainWindow = null;
let backendProcess = null;
let backendPort = null;
let backendReady = null;
let backendReadyResolve = null;
let backendReadyReject = null;

Menu.setApplicationMenu(null);
if (process.platform === 'win32') app.setAppUserModelId('com.rpgrenpylocalizer.desktop');

function projectRoot() {
  return app.isPackaged ? process.resourcesPath : app.getAppPath();
}

function findPython() {
  const root = projectRoot();
  const candidates = [
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    path.join(app.getAppPath(), '.venv', 'Scripts', 'python.exe'),
    'python',
    'py'
  ];
  return candidates.find((candidate) => candidate === 'python' || candidate === 'py' || fs.existsSync(candidate)) || 'python';
}

function backendExecutable() {
  if (!app.isPackaged) return null;
  const exe = path.join(process.resourcesPath, 'backend', 'rpgrtl-api.exe');
  return fs.existsSync(exe) ? exe : null;
}

function startBackend() {
  if (backendReady) return backendReady;
  backendReady = new Promise((resolve, reject) => {
    backendReadyResolve = resolve;
    backendReadyReject = reject;
  });

  const root = projectRoot();
  const bundled = backendExecutable();
  const command = bundled || findPython();
  const args = bundled ? ['--port', '0', '--project-root', root] : ['-m', 'toolkit.api.server', '--port', '0', '--project-root', root];

  backendProcess = spawn(command, args, {
    cwd: root,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  let stdoutBuffer = '';
  backendProcess.stdout.on('data', (chunk) => {
    const text = chunk.toString('utf8');
    stdoutBuffer += text;
    for (const line of stdoutBuffer.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const msg = JSON.parse(trimmed);
        if (msg.ready && msg.port) {
          backendPort = msg.port;
          backendReadyResolve({ port: backendPort, url: `http://127.0.0.1:${backendPort}` });
        }
      } catch (_) {
        console.log('[backend]', trimmed);
      }
    }
    const lastNewline = Math.max(stdoutBuffer.lastIndexOf('\n'), stdoutBuffer.lastIndexOf('\r'));
    if (lastNewline >= 0) stdoutBuffer = stdoutBuffer.slice(lastNewline + 1);
  });

  backendProcess.stderr.on('data', (chunk) => console.error('[backend]', chunk.toString('utf8')));
  backendProcess.on('error', (error) => {
    console.error('Backend failed:', error);
    backendReadyReject(error);
  });
  backendProcess.on('exit', (code) => {
    console.log('Backend exited', code);
    backendProcess = null;
  });

  setTimeout(() => {
    if (!backendPort) backendReadyReject(new Error('Python 后端启动超时'));
  }, 20000);
  return backendReady;
}

function rendererIndexPath() {
  return path.join(__dirname, 'renderer', 'dist', 'index.html');
}

function appIconPath() {
  return path.join(__dirname, '..', 'static', 'icon.ico');
}

async function createWindow() {
  const backend = await startBackend();
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1040,
    minHeight: 680,
    backgroundColor: '#08111d',
    title: 'RPGRenPyLocalizer',
    icon: appIconPath(),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });
  mainWindow.setMenuBarVisibility(false);
  mainWindow.setAutoHideMenuBar(true);
  const indexPath = rendererIndexPath();
  if (!fs.existsSync(indexPath)) {
    throw new Error(`未找到前端构建产物：${indexPath}。请先运行 npm run build:renderer`);
  }
  await mainWindow.loadFile(indexPath, { query: { port: String(backend.port) } });
}

ipcMain.handle('backend:getPort', async () => {
  const backend = await startBackend();
  return backend.port;
});

ipcMain.handle('dialog:selectProject', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择游戏启动程序（EXE）',
    properties: ['openFile'],
    filters: [
      { name: '游戏启动程序', extensions: ['exe'] }
    ]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:selectGameFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择包含游戏的文件夹',
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:openPack', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '导入翻译包',
    properties: ['openFile'],
    filters: [{ name: '翻译包', extensions: ['json', 'csv'] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:savePack', async () => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: '导出翻译包',
    defaultPath: 'translations.json',
    filters: [{ name: 'JSON 翻译包', extensions: ['json'] }]
  });
  return result.canceled ? null : result.filePath;
});

ipcMain.handle('shell:openPath', async (_event, targetPath) => {
  if (!targetPath) return false;
  await shell.openPath(targetPath);
  return true;
});

ipcMain.handle('shell:openExternal', async (_event, targetUrl) => {
  if (!targetUrl || !/^(https?:|mailto:)/i.test(targetUrl)) return false;
  await shell.openExternal(targetUrl);
  return true;
});

ipcMain.handle('app:getVersion', () => app.getVersion());

function commandExists(command) {
  return new Promise((resolve) => {
    const checker = process.platform === 'win32' ? 'where.exe' : 'which';
    const child = spawn(checker, [command], { windowsHide: true, stdio: 'ignore' });
    child.once('error', () => resolve(false));
    child.once('exit', (code) => resolve(code === 0));
  });
}

function geminiCredentialMarker() {
  // Deliberately only inspect file metadata. Gemini CLI owns the credential
  // and the Electron app must never read, copy, or transmit its contents.
  const file = path.join(app.getPath('home'), '.gemini', 'oauth_creds.json');
  try {
    const stat = fs.statSync(file);
    return { authenticated: stat.isFile(), updatedAt: stat.mtimeMs };
  } catch (_) {
    return { authenticated: false, updatedAt: null };
  }
}

function geminiLoginScriptPath() {
  const scriptPath = path.join(app.getPath('userData'), 'gemini-login.cmd');
  const script = [
    '@echo off',
    'chcp 65001 >nul',
    'title RPGRenPyLocalizer Gemini Login',
    'echo Starting Gemini CLI OAuth login...',
    'echo.',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "gemini -i /auth"',
    'set EXIT_CODE=%ERRORLEVEL%',
    'echo.',
    'echo Gemini CLI exited with code %EXIT_CODE%.',
    'echo You can close this window after the browser login reports success.',
    'pause',
    'exit /b %EXIT_CODE%',
    ''
  ].join('\r\n');
  fs.mkdirSync(path.dirname(scriptPath), { recursive: true });
  fs.writeFileSync(scriptPath, script, 'utf8');
  return scriptPath;
}

ipcMain.handle('account:status', async (_event, payload = {}) => {
  const provider = String(payload.provider || '').trim().toLowerCase();
  if (provider !== 'gemini-cli') return { provider, installed: null, authenticated: null };
  const marker = geminiCredentialMarker();
  return { provider, installed: await commandExists('gemini'), ...marker };
});

ipcMain.handle('account:login', async (_event, payload = {}) => {
  const providers = new Set(['openai-codex', 'anthropic', 'github-copilot', 'kimi-coding', 'xai', 'gemini-cli', 'antigravity-cli']);
  const provider = String(payload.provider || 'openai-codex').trim().toLowerCase();
  if (!providers.has(provider)) throw new Error('该账号当前没有可用的 OAuth 登录桥接。');

  if (provider === 'gemini-cli') {
    if (!(await commandExists('gemini'))) {
      throw new Error('未检测到 Gemini CLI。请先安装 Gemini CLI 后再登录。');
    }
    // `/auth` is Gemini CLI's interactive auth command. It owns the browser
    // redirect, PKCE verifier, localhost callback listener, and credential
    // store. Use a generated .cmd file instead of `cmd /c start ...`: Windows
    // `start` parsing is fragile with quoted titles and slash switches.
    const loginScript = geminiLoginScriptPath();
    const openError = await shell.openPath(loginScript);
    if (openError) throw new Error(openError);
    return { started: true, provider, mode: 'gemini-cli-oauth', script: loginScript, before: geminiCredentialMarker() };
  }

  throw new Error('此账号桥接尚未安装对应的本地 Agent 登录器。请选择 Gemini / Google，或安装对应 Agent 后再使用。');
});

ipcMain.handle('update:check', async () => {
  const currentVersion = app.getVersion();
  const tags = await new Promise((resolve, reject) => {
    const request = https.get({
      hostname: 'api.github.com',
      path: '/repos/lyb82ndkf-lab/RPG-RenPy-Localizer/tags?per_page=20',
      headers: {
        Accept: 'application/vnd.github+json',
        'User-Agent': 'RPGRenPyLocalizer',
        'X-GitHub-Api-Version': '2022-11-28'
      }
    }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { body += chunk; });
      response.on('end', () => {
        if (response.statusCode < 200 || response.statusCode >= 300) return reject(new Error(`GitHub HTTP ${response.statusCode}`));
        try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
      });
    });
    request.setTimeout(12000, () => request.destroy(new Error('检查更新超时')));
    request.on('error', reject);
  });
  const versions = Array.isArray(tags)
    ? tags.map((item) => String(item.name || '').replace(/^v/i, '')).filter((value) => /^\d+(?:\.\d+){1,3}(?:[-+].*)?$/.test(value))
    : [];
  const parts = (value) => String(value).split(/[.-]/).map((part) => Number.parseInt(part, 10) || 0);
  const compare = (left, right) => {
    const a = parts(left); const b = parts(right);
    for (let index = 0; index < Math.max(a.length, b.length); index++) {
      if ((a[index] || 0) !== (b[index] || 0)) return (a[index] || 0) - (b[index] || 0);
    }
    return 0;
  };
  versions.sort((a, b) => compare(b, a));
  const latestVersion = versions[0] || currentVersion;
  return { currentVersion, latestVersion, hasUpdate: compare(latestVersion, currentVersion) > 0 };
});

app.whenReady().then(createWindow).catch((error) => {
  dialog.showErrorBox('启动失败', String(error && error.stack ? error.stack : error));
  app.quit();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
