const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');
const crypto = require('crypto');
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

function translationPackDefaultDirectory(payload = {}) {
  const launcherPath = typeof payload.launcherPath === 'string' ? payload.launcherPath : '';
  const gamePath = typeof payload.gamePath === 'string' ? payload.gamePath : '';
  for (const candidate of [launcherPath, gamePath]) {
    if (!candidate || !fs.existsSync(candidate)) continue;
    try {
      return fs.statSync(candidate).isDirectory() ? candidate : path.dirname(candidate);
    } catch (_) { /* Try the next verified candidate. */ }
  }
  return undefined;
}

ipcMain.handle('dialog:openPack', async (_event, payload = {}) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '导入翻译包',
    defaultPath: translationPackDefaultDirectory(payload),
    properties: ['openFile'],
    filters: [{ name: '翻译包', extensions: ['json', 'csv'] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:savePack', async (_event, payload = {}) => {
  const directory = translationPackDefaultDirectory(payload);
  const result = await dialog.showSaveDialog(mainWindow, {
    title: '导出翻译包',
    defaultPath: directory ? path.join(directory, 'translations.json') : 'translations.json',
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
  const file = accountCredentialPath('google-gemini-cli');
  try {
    const stat = fs.statSync(file);
    return { authenticated: stat.isFile(), updatedAt: stat.mtimeMs };
  } catch (_) {
    return { authenticated: false, updatedAt: null };
  }
}

function accountCredentialPath(provider) {
  const appdata = process.env.APPDATA || path.join(app.getPath('home'), 'AppData', 'Roaming');
  return path.join(appdata, 'RPGRenPyLocalizer', `${provider}-oauth.json`);
}

function randomHex(bytes = 16) {
  return crypto.randomBytes(bytes).toString('hex');
}

function jsonResponse(res, status, payload) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function htmlResponse(res, status, title, message) {
  res.writeHead(status, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`<!doctype html><meta charset="utf-8"><title>${title}</title><body style="font-family:system-ui;margin:48px;line-height:1.6"><h2>${title}</h2><p>${message}</p><p>可以关闭这个页面，回到 RPGRenPyLocalizer。</p></body>`);
}

function postForm(url, values) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams(values).toString();
    const request = https.request(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (response) => {
      let data = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { data += chunk; });
      response.on('end', () => {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          return reject(new Error(`HTTP ${response.statusCode}: ${data}`));
        }
        try { resolve(JSON.parse(data)); } catch (error) { reject(error); }
      });
    });
    request.on('error', reject);
    request.write(body);
    request.end();
  });
}

function requestJson(url, options = {}) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const body = options.body ? JSON.stringify(options.body) : '';
    const request = https.request(target, {
      method: options.method || 'GET',
      headers: {
        ...(body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {}),
        ...(options.headers || {})
      }
    }, (response) => {
      let data = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { data += chunk; });
      response.on('end', () => {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          return reject(new Error(`HTTP ${response.statusCode}: ${data}`));
        }
        try { resolve(data ? JSON.parse(data) : {}); } catch (error) { reject(error); }
      });
    });
    request.on('error', reject);
    if (body) request.write(body);
    request.end();
  });
}

const GOOGLE_GEMINI_OAUTH = {
  provider: 'google-gemini-cli',
  clientId: process.env.GOOGLE_GEMINI_CLIENT_ID || '',
  clientSecret: process.env.GOOGLE_GEMINI_CLIENT_SECRET || '',
  callbackPort: 8085,
  callbackPath: '/oauth2callback',
  scopes: [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
  ],
  authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
  tokenUrl: 'https://oauth2.googleapis.com/token',
  endpoint: 'https://cloudcode-pa.googleapis.com'
};

async function getGoogleUserEmail(accessToken) {
  try {
    const data = await requestJson('https://www.googleapis.com/oauth2/v1/userinfo?alt=json', {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    return typeof data.email === 'string' ? data.email : '';
  } catch (_) {
    return '';
  }
}

async function discoverGoogleCloudCodeProject(accessToken) {
  const headers = {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
    'User-Agent': 'GeminiCLI/0.49.0/gemini-2.5-flash (win32; x64; terminal)',
    'Client-Metadata': 'ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI'
  };
  const envProjectId = process.env.GOOGLE_CLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT_ID || '';
  const metadata = {
    ideType: 'IDE_UNSPECIFIED',
    platform: 'PLATFORM_UNSPECIFIED',
    pluginType: 'GEMINI',
    ...(envProjectId ? { duetProject: envProjectId } : {})
  };
  const load = await requestJson(`${GOOGLE_GEMINI_OAUTH.endpoint}/v1internal:loadCodeAssist`, {
    method: 'POST',
    headers,
    body: { cloudaicompanionProject: envProjectId || undefined, metadata }
  });
  const loadedProject = extractGoogleProjectId(load);
  if (loadedProject) return loadedProject;
  if (load.currentTier && envProjectId) return envProjectId;

  const allowed = Array.isArray(load.allowedTiers) ? load.allowedTiers : [];
  const tier = load.currentTier || allowed.find((item) => item && item.isDefault) || allowed[0] || { id: 'free-tier' };
  const onboard = await requestJson(`${GOOGLE_GEMINI_OAUTH.endpoint}/v1internal:onboardUser`, {
    method: 'POST',
    headers,
    body: {
      tierId: tier.id || 'free-tier',
      ...(tier.id !== 'free-tier' && envProjectId ? { cloudaicompanionProject: envProjectId } : {}),
      metadata
    }
  });
  const onboardProject = extractGoogleProjectId(onboard);
  if (onboardProject) return onboardProject;
  if (!onboard.done && onboard.name) {
    const operation = await pollGoogleOperation(onboard.name, headers);
    const operationProject = extractGoogleProjectId(operation);
    if (operationProject) return operationProject;
  }
  if (envProjectId) return envProjectId;
  throw new Error('Gemini 授权已完成，但 Cloud Code Assist 没有返回可用 projectId。请稍后重试登录，或换用个人 Google/Gemini 账号。');
}

function extractGoogleProjectId(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const direct = payload.cloudaicompanionProject;
  if (typeof direct === 'string') return direct;
  if (direct && typeof direct.id === 'string') return direct.id;
  const nested = payload.response && payload.response.cloudaicompanionProject;
  if (typeof nested === 'string') return nested;
  if (nested && typeof nested.id === 'string') return nested.id;
  return '';
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollGoogleOperation(operationName, headers) {
  let last = {};
  for (let attempt = 0; attempt < 24; attempt += 1) {
    if (attempt > 0) await delay(5000);
    last = await requestJson(`${GOOGLE_GEMINI_OAUTH.endpoint}/v1internal/${operationName}`, {
      method: 'GET',
      headers
    });
    if (last.done) return last;
  }
  return last;
}

function startGoogleGeminiOAuthLogin() {
  return new Promise((resolve, reject) => {
    const state = randomHex(16);
    const redirectUri = `http://127.0.0.1:${GOOGLE_GEMINI_OAUTH.callbackPort}${GOOGLE_GEMINI_OAUTH.callbackPath}`;
    let authUrl = '';
    const server = http.createServer(async (req, res) => {
      try {
        const url = new URL(req.url || '/', `http://127.0.0.1:${GOOGLE_GEMINI_OAUTH.callbackPort}`);
        if (url.pathname === '/launch') {
          res.writeHead(302, { Location: authUrl });
          res.end();
          return;
        }
        if (url.pathname !== GOOGLE_GEMINI_OAUTH.callbackPath) {
          return htmlResponse(res, 404, 'Not Found', 'OAuth 登录地址无效。');
        }
        const error = url.searchParams.get('error');
        if (error) {
          htmlResponse(res, 500, 'Gemini 授权失败', url.searchParams.get('error_description') || error);
          server.close();
          reject(new Error(url.searchParams.get('error_description') || error));
          return;
        }
        const code = url.searchParams.get('code');
        if (!code || url.searchParams.get('state') !== state) {
          htmlResponse(res, 500, 'Gemini 授权失败', '回调参数不完整或 state 校验失败。');
          server.close();
          reject(new Error('Gemini OAuth 回调参数无效。'));
          return;
        }
        const token = await postForm(GOOGLE_GEMINI_OAUTH.tokenUrl, {
          client_id: GOOGLE_GEMINI_OAUTH.clientId,
          client_secret: GOOGLE_GEMINI_OAUTH.clientSecret,
          code,
          grant_type: 'authorization_code',
          redirect_uri: redirectUri
        });
        if (!token.refresh_token) throw new Error('Google 没有返回 refresh_token，请重新授权。');
        const email = await getGoogleUserEmail(token.access_token);
        let projectId = '';
        let projectDiscoveryError = '';
        try {
          projectId = await discoverGoogleCloudCodeProject(token.access_token);
        } catch (error) {
          projectDiscoveryError = String(error.message || error);
        }
        const credential = {
          provider: GOOGLE_GEMINI_OAUTH.provider,
          refresh: token.refresh_token,
          access: token.access_token,
          expires: Date.now() + Number(token.expires_in || 3600) * 1000 - 5 * 60 * 1000,
          projectId,
          email,
          projectDiscoveryError,
          updatedAt: Date.now()
        };
        const credentialPath = accountCredentialPath(GOOGLE_GEMINI_OAUTH.provider);
        fs.mkdirSync(path.dirname(credentialPath), { recursive: true });
        fs.writeFileSync(credentialPath, JSON.stringify(credential, null, 2), 'utf8');
        htmlResponse(
          res,
          200,
          'Gemini 账号授权成功',
          projectId
            ? (email ? `已登录 ${email}，Cloud Code Assist 已准备好。` : '授权已完成，Cloud Code Assist 已准备好。')
            : (email ? `已登录 ${email}。Cloud Code Assist 暂未返回 projectId，软件会自动使用 Gemini OAuth 兼容模式。` : '授权已完成。Cloud Code Assist 暂未返回 projectId，软件会自动使用 Gemini OAuth 兼容模式。')
        );
        server.close();
        resolve({ started: true, authenticated: true, provider: 'gemini-cli', email, projectId, projectDiscoveryError });
      } catch (error) {
        htmlResponse(res, 500, 'Gemini 授权失败', String(error.message || error));
        server.close();
        reject(error);
      }
    });
    server.once('error', (error) => {
      reject(new Error(`无法启动 OAuth 回调服务：${error.message}`));
    });
    server.listen(GOOGLE_GEMINI_OAUTH.callbackPort, '127.0.0.1', async () => {
      const params = new URLSearchParams({
        client_id: GOOGLE_GEMINI_OAUTH.clientId,
        response_type: 'code',
        redirect_uri: redirectUri,
        scope: GOOGLE_GEMINI_OAUTH.scopes.join(' '),
        state,
        access_type: 'offline',
        prompt: 'consent'
      });
      authUrl = `${GOOGLE_GEMINI_OAUTH.authUrl}?${params.toString()}`;
      const launchUrl = `http://127.0.0.1:${GOOGLE_GEMINI_OAUTH.callbackPort}/launch`;
      const openError = await shell.openExternal(launchUrl);
      if (openError) {
        server.close();
        reject(new Error(openError));
        return;
      }
      resolve({ started: true, provider: 'gemini-cli', mode: 'google-browser-oauth', launchUrl, before: geminiCredentialMarker() });
    });
  });
}

ipcMain.handle('account:status', async (_event, payload = {}) => {
  const provider = String(payload.provider || '').trim().toLowerCase();
  if (provider !== 'gemini-cli') return { provider, installed: null, authenticated: null };
  const marker = geminiCredentialMarker();
  return { provider, installed: true, ...marker };
});

ipcMain.handle('account:login', async (_event, payload = {}) => {
  const providers = new Set(['local-agent-auto', 'openai-codex', 'anthropic', 'github-copilot', 'kimi-coding', 'xai', 'gemini-cli', 'antigravity-cli', 'opencode']);
  const provider = String(payload.provider || 'openai-codex').trim().toLowerCase();
  if (!providers.has(provider)) throw new Error('该账号当前没有可用的 OAuth 登录桥接。');

  if (provider === 'gemini-cli') {
    return startGoogleGeminiOAuthLogin();
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
