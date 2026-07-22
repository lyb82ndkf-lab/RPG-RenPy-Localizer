const state = {
  apiBase: '',
  entries: [],
  filtered: [],
  selectedPath: '',
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
}

function toast(message, error = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('error', error);
  el.classList.add('show');
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => el.classList.remove('show'), 2600);
}

async function api(path, options = {}) {
  const method = options.method || (options.body ? 'POST' : 'GET');
  const res = await fetch(state.apiBase + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.ok === false) throw new Error(json.error || `HTTP ${res.status}`);
  return json.data;
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.oldText = button.textContent;
    button.textContent = label || '处理中...';
    button.disabled = true;
  } else {
    button.textContent = button.dataset.oldText || button.textContent;
    button.disabled = false;
  }
}

function formatTime(value) {
  return value ? String(value) : '—';
}

function updateStatus(projectCount = null) {
  $('libraryCount').textContent = String(projectCount ?? state.entries.length);
  $('visibleCount').textContent = String(state.filtered.length);
}

function applyFilter() {
  const q = $('searchBox').value.trim().toLowerCase();
  state.filtered = state.entries.filter((entry) => {
    if (!q) return true;
    return [entry.name, entry.path, entry.engine, entry.launcher_path, entry.note]
      .some((value) => String(value || '').toLowerCase().includes(q));
  });
  renderLibrary();
}

function renderLibrary() {
  const list = $('libraryList');
  updateStatus();
  if (!state.filtered.length) {
    list.innerHTML = '<div class="empty-list">没有找到游戏，先点击“添加游戏”。</div>';
    if (!state.entries.length) {
      clearDetail();
    }
    return;
  }
  list.innerHTML = state.filtered.map((entry) => {
    const selected = entry.path === state.selectedPath ? 'selected' : '';
    return `
      <button class="library-item ${selected}" data-path="${escapeHtml(entry.path)}">
        <strong>${escapeHtml(entry.name || '未命名')}</strong>
        <span>${escapeHtml(entry.engine || '未知引擎')}</span>
        <em>${escapeHtml(entry.path)}</em>
      </button>`;
  }).join('');
  list.querySelectorAll('.library-item').forEach((item) => {
    item.addEventListener('click', () => selectEntry(item.dataset.path));
  });
  if (!state.filtered.some((entry) => entry.path === state.selectedPath)) {
    selectEntry(state.filtered[0].path, false);
  }
}

function clearDetail() {
  $('emptyState').classList.remove('hidden');
  $('detailView').classList.add('hidden');
  $('selectedState').textContent = '未选择';
  state.selectedPath = '';
}

function selectEntry(path, rerender = true) {
  const entry = state.entries.find((item) => item.path === path);
  if (!entry) {
    clearDetail();
    return;
  }
  state.selectedPath = entry.path;
  $('emptyState').classList.add('hidden');
  $('detailView').classList.remove('hidden');
  $('selectedState').textContent = '已选中';
  $('detailName').textContent = entry.name || '未命名';
  $('detailEngine').textContent = entry.engine || '未知引擎';
  $('detailPath').textContent = entry.path || '—';
  $('detailLauncher').textContent = entry.launcher_path || '—';
  $('detailAdded').textContent = formatTime(entry.added_at);
  $('detailOpened').textContent = formatTime(entry.last_opened_at);
  if (rerender) renderLibrary();
}

async function loadLibrary() {
  const data = await api('/library');
  state.entries = data.entries || [];
  state.filtered = [...state.entries];
  if (!state.entries.length) {
    clearDetail();
  } else if (state.selectedPath && !state.entries.some((entry) => entry.path === state.selectedPath)) {
    state.selectedPath = '';
  }
  renderLibrary();
}

async function addGame() {
  const path = await window.rpgrtl.selectProject();
  if (!path) return;
  const btn = $('addGameBtn');
  setBusy(btn, true, '添加中...');
  try {
    await api('/library/add', { body: { path } });
    await loadLibrary();
    toast('游戏已加入库');
  } finally {
    setBusy(btn, false);
  }
}

async function launchGame() {
  if (!state.selectedPath) return toast('请先选择一个游戏', true);
  const entry = state.entries.find((item) => item.path === state.selectedPath);
  if (!entry) return toast('条目不存在', true);
  const btn = $('launchBtn');
  setBusy(btn, true, '启动中...');
  try {
    const data = await api('/library/launch', { body: { path: entry.path } });
    toast(`游戏已启动 PID ${data.pid}`);
    await loadLibrary();
    selectEntry(entry.path, true);
  } finally {
    setBusy(btn, false);
  }
}

async function openFolder() {
  if (!state.selectedPath) return toast('请先选择一个游戏', true);
  await window.rpgrtl.openPath(state.selectedPath);
}

async function removeGame() {
  if (!state.selectedPath) return toast('请先选择一个游戏', true);
  const entry = state.entries.find((item) => item.path === state.selectedPath);
  if (!entry) return;
  if (!confirm(`确定移除【${entry.name || '未命名'}】吗？`)) return;
  const btn = $('removeBtn');
  setBusy(btn, true, '移除中...');
  try {
    await api('/library/remove', { body: { path: entry.path } });
    await loadLibrary();
    toast('已移除');
  } finally {
    setBusy(btn, false);
  }
}

async function refresh() {
  const btn = $('refreshBtn');
  setBusy(btn, true, '刷新中...');
  try {
    await loadLibrary();
    toast('已刷新');
  } finally {
    setBusy(btn, false);
  }
}

function bindEvents() {
  $('addGameBtn').addEventListener('click', () => addGame().catch((e) => toast(e.message, true)));
  $('refreshBtn').addEventListener('click', () => refresh().catch((e) => toast(e.message, true)));
  $('searchBox').addEventListener('input', () => applyFilter());
  $('launchBtn').addEventListener('click', () => launchGame().catch((e) => toast(e.message, true)));
  $('openFolderBtn').addEventListener('click', () => openFolder().catch((e) => toast(e.message, true)));
  $('removeBtn').addEventListener('click', () => removeGame().catch((e) => toast(e.message, true)));
}

async function init() {
  bindEvents();
  const params = new URLSearchParams(location.search);
  const port = params.get('port') || await window.rpgrtl.backendPort();
  state.apiBase = `http://127.0.0.1:${port}`;
  $('backendUrl').textContent = state.apiBase;
  try {
    const health = await api('/health');
    $('backendDot').classList.add('ok');
    $('backendStatus').textContent = `Python ${health.python}`;
    await loadLibrary();
  } catch (e) {
    $('backendDot').classList.add('bad');
    $('backendStatus').textContent = '后端异常';
    toast(e.message, true);
  }
}

init().catch((e) => toast(e.message, true));
