(function () {
  if (window.__rpgrtlGameErrorCollector) return;
  window.__rpgrtlGameErrorCollector = true;
  function send(payload) {
    try {
      if (window.RPGRenPyGameBridge && window.RPGRenPyGameBridge.androidJsError) {
        window.RPGRenPyGameBridge.androidJsError(JSON.stringify(payload));
      }
    } catch (e) {}
  }
  window.onerror = function (msg, url, line, col, err) {
    send({
      type: 'error',
      message: String(msg || ''),
      url: String(url || ''),
      line: line || 0,
      col: col || 0,
      stack: err && err.stack ? String(err.stack).slice(0, 500) : ''
    });
    return false;
  };
  window.addEventListener('unhandledrejection', function (e) {
    send({
      type: 'promise',
      reason: String((e && e.reason) || '').slice(0, 500)
    });
  });
})();
