from __future__ import annotations

import re
import shutil
import json
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import DataRecord, ProjectInfo, TranslationEntry


STRING_PATTERN = re.compile(r'^\s*old\s+"(?P<old>(?:[^"\\]|\\.)*)"\s*$')
QUOTE_PATTERN = re.compile(
    r'^(?P<indent>\s*)(?P<speaker>[A-Za-z_][\w]*)?\s*"(?P<text>(?:[^"\\]|\\.)*)"(?:\s+.*)?$'
)
MENU_CHOICE_SUFFIX_PATTERN = re.compile(r'^\s*(?:if\b.+)?\s*:\s*(?:#.*)?$')
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
PASTED_PLACEHOLDER_PATTERN = re.compile(r"\[?\s*Pasted\s+~?\d+\s+lines?\s*\]?", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][\w]*$")
RPA_TEXT_PATTERN = re.compile(rb"[\x20-\x7e\x80-\xff]{4,}")
RUNTIME_PATCH_NAME = "zz_rpgrtl_runtime_translation.rpy"
EMBEDDED_PATCH_NAME = "zz_rpgrtl_embedded_translation.rpy"
LANGUAGE_BOOTSTRAP_NAME = "zz_rpgrtl_language.rpy"
EXTRACTOR_NAME = "zz_rpgrtl_extract.rpy"
RESOURCE_PREP_NAME = "zz_rpgrtl_prepare_renpy.py"
LIVE_BRIDGE_NAME = "zz_rpgrtl_live_bridge.rpy"
LIVE_TRANSLATIONS_NAME = "renpy_live_translation.json"
LIVE_SEEN_NAME = "renpy_live_seen.jsonl"
LIVE_LOG_NAME = "rpgrtl_live_debug.log"
LIVE_BRIDGE_PORT = 32180
LIVE_BRIDGE_VERSION = "2026-05-29.6"

_LIVE_SERVER_LOCK = threading.Lock()
_LIVE_SERVER: ThreadingHTTPServer | None = None
_LIVE_SERVER_STATE: dict[str, object] = {"translations": {}, "events": [], "seen": {}, "notify_seq": 0, "force_text": "", "pre_translate_queue": []}


def _live_log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / LIVE_LOG_NAME
    return Path(__file__).resolve().parents[1] / LIVE_LOG_NAME


def _append_live_log(component: str, event: str, payload: object = "") -> None:
    try:
        line = json.dumps(
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "component": component,
                "event": event,
                "payload": payload,
            },
            ensure_ascii=False,
        )
        with _LIVE_LOG_LOCK:
            _LIVE_LOG_BUFFER.append(line)
            if len(_LIVE_LOG_BUFFER) >= 20:
                _flush_live_log_buffer()
    except Exception:
        pass

_LIVE_LOG_BUFFER: list[str] = []
_LIVE_LOG_LOCK = threading.Lock()
_LIVE_LOG_LAST_FLUSH = 0.0

def _flush_live_log_buffer() -> None:
    global _LIVE_LOG_LAST_FLUSH
    if not _LIVE_LOG_BUFFER:
        return
    try:
        path = _live_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            for line in _LIVE_LOG_BUFFER:
                f.write(line + "\n")
        _LIVE_LOG_BUFFER.clear()
        _LIVE_LOG_LAST_FLUSH = time.time()
    except Exception:
        pass


def _live_translation_candidates(source: str, transformed: str | None = None) -> list[str]:
    values = [source]
    if transformed is not None and transformed != source:
        values.insert(0, transformed)
    candidates: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        stripped = value.strip()
        variants = [value, stripped, re.sub(r"\{[^}]*\}", "", stripped).strip(), re.sub(r"\s+", " ", stripped)]
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
            variants.append(stripped[1:-1])
        for item in variants:
            if item and item not in seen:
                seen.add(item)
                candidates.append(item)
    return candidates


def _lookup_live_translation_value(translations: dict, source: str, transformed: str | None = None) -> str:
    for key in _live_translation_candidates(source, transformed):
        if key in translations:
            return str(translations.get(key) or "")
    return ""


class _RenPyLiveBridgeHandler(BaseHTTPRequestHandler):
    server_version = "RPGRenPyLiveBridge/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            payload = self.rfile.read(length).decode("utf-8")
            data = json.loads(payload)
            return data if (hasattr(data, "get") and hasattr(data, "keys")) else {}
        except Exception:
            return {}

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/notify":
            with _LIVE_SERVER_LOCK:
                seq = int(_LIVE_SERVER_STATE.get("notify_seq", 0))
                force_text = str(_LIVE_SERVER_STATE.get("force_text", "") or "")
                force_seq = int(_LIVE_SERVER_STATE.get("force_seq", 0))
                if force_text:
                    _LIVE_SERVER_STATE["force_text"] = ""
            self._send_json({"ok": True, "seq": seq, "force_text": force_text, "force_seq": force_seq})
            return
        if parsed.path != "/debug":
            self._send_json({"ok": False, "error": "not found"})
            return
        params = parse_qs(parsed.query)
        limit = 300
        try:
            limit = max(1, min(1000, int(params.get("limit", ["300"])[0])))
        except (TypeError, ValueError):
            pass
        with _LIVE_SERVER_LOCK:
            events = list(_LIVE_SERVER_STATE.get("events", []))[-limit:]
            translation_count = len(_LIVE_SERVER_STATE.get("translations", {}))
        self._send_json({"ok": True, "events": events, "translation_count": translation_count})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        if parsed.path == "/notify":
            with _LIVE_SERVER_LOCK:
                seq = int(_LIVE_SERVER_STATE.get("notify_seq", 0))
                force_text = str(_LIVE_SERVER_STATE.get("force_text", "") or "")
                force_seq = int(_LIVE_SERVER_STATE.get("force_seq", 0))
                if force_text:
                    _LIVE_SERVER_STATE["force_text"] = ""
            self._send_json({"ok": True, "seq": seq, "force_text": force_text, "force_seq": force_seq})
            return
        if parsed.path == "/log":
            _append_live_log("game", str(payload.get("event", "log") or "log"), payload)
            self._send_json({"ok": True})
            return
        if parsed.path == "/pull":
            with _LIVE_SERVER_LOCK:
                translations = dict(_LIVE_SERVER_STATE.get("translations", {}))
            self._send_json({"ok": True, "translations": translations})
            return
        if parsed.path == "/translation":
            source = str(payload.get("text", "") or "")
            displayed = str(payload.get("substituted", "") or source)
            with _LIVE_SERVER_LOCK:
                translations = _LIVE_SERVER_STATE.get("translations", {})
            target = _lookup_live_translation_value(translations, source, displayed)
            if target:
                self._send_json({"code": 0, "ok": True, "new_text": target})
            else:
                self._send_json({"code": -1, "ok": False, "error": "not found"})
            return
        if parsed.path == "/boot":
            event = {
                "time": time.time(),
                "kind": "boot",
                "source": str(payload.get("root", "")),
                "displayed": str(payload.get("version", "")),
                "target": "",
                "matched": False,
                "pid": payload.get("pid", ""),
            }
            with _LIVE_SERVER_LOCK:
                _LIVE_SERVER_STATE.setdefault("events", []).append(event)
            _append_live_log("game", "boot", event)
            self._send_json({"ok": True})
            return
        if parsed.path == "/seen":
            source = str(payload.get("what", "") or "")
            displayed = str(payload.get("displayed", "") or source)
            kind = str(payload.get("event", "seen") or "seen")
            allowed_events = {
                "prefix_suffix",
                "do_display",
                "do_display_raw",
                "do_display_displayed",
                "display_say",
                "show_display_say",
                "text_init",
                "choice",
                "menu_choice",
                "who",
                "live_pulled",
                "live_replaced",
                "live_replace_failed",
                "live_bridge_loaded",
                "live_refresh",
            }
            if kind not in allowed_events:
                self._send_json({"ok": True, "target": ""})
                return
            with _LIVE_SERVER_LOCK:
                translations = _LIVE_SERVER_STATE.get("translations", {})
            target = str(payload.get("target", "") or "")
            if not target:
                target = _lookup_live_translation_value(translations, source, displayed)
            matched = bool(payload.get("matched") or (target and target != displayed))
            event = {
                "time": time.time(),
                "kind": kind,
                "source": source,
                "displayed": displayed,
                "target": target,
                "matched": matched,
                "type": str(payload.get("type", "") or ""),
                "interact": bool(payload.get("interact", True)),
            }
            if source.strip() or displayed.strip():
                with _LIVE_SERVER_LOCK:
                    seen = _LIVE_SERVER_STATE.setdefault("seen", {})
                    key = source or displayed
                    previous = seen.get(key) if isinstance(seen, dict) else None
                    if previous != target:
                        if isinstance(seen, dict):
                            seen[key] = target
                        _LIVE_SERVER_STATE.setdefault("events", []).append(event)
                        events = _LIVE_SERVER_STATE.get("events", [])
                        if isinstance(events, list) and len(events) > 2000:
                            del events[: len(events) - 2000]
                    _append_live_log("game", "seen", event)
            self._send_json({"ok": True, "target": target})
            return
        if parsed.path == "/pre_translate":
            texts = payload.get("texts", []) if hasattr(payload, "get") else []
            if not isinstance(texts, list):
                texts = []
            with _LIVE_SERVER_LOCK:
                translations = dict(_LIVE_SERVER_STATE.get("translations", {}))
                pre_queue = _LIVE_SERVER_STATE.setdefault("pre_translate_queue", [])
            found = {}
            queued = []
            for text in texts:
                if not isinstance(text, str) or not text.strip():
                    continue
                target = _lookup_live_translation_value(translations, text, text)
                if target:
                    found[text] = target
                else:
                    if text not in pre_queue:
                        pre_queue.append(text)
                    queued.append(text)
            _append_live_log("server", "pre_translate", {"total": len(texts), "found": len(found), "queued": len(queued)})
            self._send_json({"ok": True, "translations": found, "queued": queued})
            return
        if parsed.path == "/seen_batch":
            items = payload.get("items", []) if hasattr(payload, "get") else []
            if not isinstance(items, list):
                items = []
            with _LIVE_SERVER_LOCK:
                seen_dict = _LIVE_SERVER_STATE.setdefault("seen", {})
                events_list = _LIVE_SERVER_STATE.setdefault("events", [])
                trans = _LIVE_SERVER_STATE.get("translations", {})
            targets = []
            for item in items:
                if not (hasattr(item, "get") and hasattr(item, "keys")):
                    targets.append("")
                    continue
                source = str(item.get("what", "") or "")
                displayed = str(item.get("displayed", "") or source)
                kind = str(item.get("event", "") or "")
                target = str(item.get("target", "") or "")
                if not target:
                    target = _lookup_live_translation_value(trans, source, displayed)
                matched = bool(item.get("matched") or (target and target != displayed))
                event = {"time": time.time(), "kind": kind, "source": source, "displayed": displayed, "target": target, "matched": matched}
                if source.strip() or displayed.strip():
                    key = source or displayed
                    previous = seen_dict.get(key) if isinstance(seen_dict, dict) else None
                    if previous != target:
                        if isinstance(seen_dict, dict):
                            seen_dict[key] = target
                        events_list.append(event)
                        if len(events_list) > 2000:
                            del events_list[:len(events_list) - 2000]
                targets.append(target)
            _append_live_log("server", "seen_batch", {"count": len(items)})
            self._send_json({"ok": True, "targets": targets})
            return
        if parsed.path == "/translation_batch":
            texts = payload.get("texts", []) if hasattr(payload, "get") else []
            if not isinstance(texts, list):
                texts = []
            with _LIVE_SERVER_LOCK:
                trans = _LIVE_SERVER_STATE.get("translations", {})
            results = {}
            for text in texts:
                if not isinstance(text, str) or not text.strip():
                    continue
                t = _lookup_live_translation_value(trans, text, text)
                if t:
                    results[text] = t
            self._send_json({"ok": True, "translations": results})
            return
        self._send_json({"ok": False, "error": "not found"})

RENPLY_RUNTIME_EXTRACTOR_SOURCE = r'''
# Auto-generated by RPGRenPyLocalizer.
# This file asks Ren'Py itself to export dialogue/string metadata from compiled scripts.
init 999 python:
    def _rpgrtl_export_texts():
        try:
            import os
            import json
            import renpy

            base_dir = os.path.dirname(config.gamedir)
            work_dir = os.path.join(base_dir, ".rpgrtl_workspace")
            if not os.path.isdir(work_dir):
                os.makedirs(work_dir)
            output = os.path.join(work_dir, "renpy_extracted.json")
            entries = []
            seen = set()

            def _clean(value):
                if value is None:
                    return ""
                try:
                    return str(value)
                except Exception:
                    return repr(value)

            def _add(category, source, file_name, context, line, identifier):
                source = _clean(source).strip()
                if not source:
                    return
                key = (category, _clean(file_name), _clean(context), source)
                if key in seen:
                    return
                seen.add(key)
                entries.append({
                    "category": category,
                    "source": source,
                    "file": _clean(file_name),
                    "context": _clean(context),
                    "line": int(line or 0),
                    "identifier": _clean(identifier),
                })

            translator = renpy.game.script.translator
            translate_say_type = getattr(renpy.ast, "TranslateSay", None)
            menu_type = getattr(renpy.ast, "Menu", None)
            for filename, translates in getattr(translator, "file_translates", {}).items():
                for _label, translate_node in translates:
                    if translate_say_type is not None and isinstance(translate_node, translate_say_type):
                        block = [translate_node]
                    else:
                        block = getattr(translate_node, "block", []) or []
                    for node in block:
                        if isinstance(node, renpy.ast.Say):
                            _add(
                                "dialogue",
                                getattr(node, "what", ""),
                                getattr(translate_node, "filename", filename),
                                getattr(node, "who", "") or "narrator",
                                getattr(node, "linenumber", getattr(translate_node, "linenumber", 0)),
                                getattr(translate_node, "identifier", ""),
                            )
                        elif menu_type is not None and isinstance(node, menu_type):
                            for item_index, item in enumerate(getattr(node, "items", []) or []):
                                caption = ""
                                if isinstance(item, (list, tuple)) and item:
                                    caption = item[0]
                                else:
                                    caption = getattr(item, "caption", "") or getattr(item, "label", "")
                                _add(
                                    "choice",
                                    caption,
                                    getattr(translate_node, "filename", filename),
                                    "menu choice",
                                    getattr(node, "linenumber", getattr(translate_node, "linenumber", 0)),
                                    "%s::choice::%s" % (getattr(translate_node, "identifier", ""), item_index),
                                )

            try:
                strings = renpy.translation.scanstrings.scan(0, 2147483647, False)
                for item in strings:
                    _add(
                        "system",
                        getattr(item, "text", ""),
                        getattr(item, "filename", ""),
                        "string",
                        getattr(item, "line", 0),
                        getattr(item, "text", ""),
                    )
            except Exception as exc:
                entries.append({
                    "category": "system",
                    "source": "",
                    "file": "scanstrings",
                    "context": "error: %s" % exc,
                    "line": 0,
                    "identifier": "",
                })

            with open(output, "w", encoding="utf-8") as f:
                json.dump({"ok": True, "entries": entries}, f, ensure_ascii=False, indent=2)
            print("RPGRenPyLocalizer exported %d Ren'Py text entries to %s" % (len(entries), output))
        except Exception as exc:
            try:
                import os
                import json
                base_dir = os.path.dirname(config.gamedir)
                work_dir = os.path.join(base_dir, ".rpgrtl_workspace")
                if not os.path.isdir(work_dir):
                    os.makedirs(work_dir)
                with open(os.path.join(work_dir, "renpy_extracted.json"), "w", encoding="utf-8") as f:
                    json.dump({"ok": False, "error": str(exc), "entries": []}, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    try:
        config.start_callbacks.append(_rpgrtl_export_texts)
    except Exception:
        try:
            config.after_load_callbacks.append(_rpgrtl_export_texts)
        except Exception:
            _rpgrtl_export_texts()
'''


RENPY_LIVE_BRIDGE_SOURCE = r'''# Auto-generated by RPGRenPyLocalizer.
# Live text bridge based on projz_renpy_translation's proven hook pattern.
init -7 python:
    import os
    import json
    import re
    import time
    import threading

    try:
        import urllib2
    except Exception:
        import urllib.request as urllib2

    try:
        string_types = (basestring,)
    except NameError:
        string_types = (str,)

    _rpgrtl_live_server = "http://127.0.0.1:__RPGRTL_PORT__"
    _rpgrtl_bridge_version = "__RPGRTL_BRIDGE_VERSION__"
    _rpgrtl_request_timeout = 0.4
    _rpgrtl_translation_cache = {}
    _rpgrtl_local_cache = {}
    _rpgrtl_pending_seen = []
    _rpgrtl_pending_lookup = set()
    _rpgrtl_translatable_cache = {}  # {text: bool} — avoids regex every frame
    _rpgrtl_last_restart_interaction = 0
    _rpgrtl_restart_interval = 0.1
    _rpgrtl_last_notify_seq = 0
    _rpgrtl_bg_loop_interval = 1.0
    _rpgrtl_tid_what = (None, None)
    _rpgrtl_active_widget = None
    _rpgrtl_active_source = ""
    _rpgrtl_force_text = ""
    _rpgrtl_force_applied = False
    _rpgrtl_debug_file = os.path.join(os.path.dirname(config.gamedir), ".rpgrtl_workspace", "rpgrtl_bridge_debug.log")
    _rpgrtl_local_cache_file = os.path.join(os.path.dirname(config.gamedir), ".rpgrtl_workspace", "renpy_live_translation.json")

    # CJK font setup — ensure Chinese characters render correctly
    try:
        _rpgrtl_cjk_font = None
        for _f in (
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ):
            if os.path.exists(_f):
                _rpgrtl_cjk_font = _f
                break
        if _rpgrtl_cjk_font:
            try:
                config.default_font = _rpgrtl_cjk_font
            except Exception:
                pass
            try:
                gui.text_font = _rpgrtl_cjk_font
            except Exception:
                pass
            try:
                gui.name_text_font = _rpgrtl_cjk_font
            except Exception:
                pass
            try:
                gui.interface_text_font = _rpgrtl_cjk_font
            except Exception:
                pass
            for _sname in (
                "default", "say_dialogue", "say_label", "say_thought",
                "input", "input_prompt",
                "choice_button_text", "choice_chosen_button_text",
                "menu_choice", "menu_choice_chosen",
                "menu_choice_button_text", "menu_choice_chosen_button_text",
                "button_text", "small_button_text",
                "navigation_button_text",
                "page_button_text",
                "quick_button_text",
                "slot_button_text",
                "label_text", "prompt_text",
                "textbutton_text",
            ):
                try:
                    getattr(style, _sname).font = _rpgrtl_cjk_font
                except Exception:
                    pass
    except Exception:
        pass

    _rpgrtl_debug_buffer = []
    _rpgrtl_debug_last_flush = 0.0
    def _rpgrtl_debug(msg):
        try:
            _rpgrtl_debug_buffer.append(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
            now = time.time()
            if len(_rpgrtl_debug_buffer) >= 10 or now - _rpgrtl_debug_last_flush >= 3.0:
                with open(_rpgrtl_debug_file, "a", encoding="utf-8") as f:
                    for line in _rpgrtl_debug_buffer:
                        f.write(line)
                _rpgrtl_debug_buffer[:] = []
                _rpgrtl_debug_last_flush = now
        except Exception:
            pass

    def _rpgrtl_send(endpoint, payload, timeout=None):
        if timeout is None:
            timeout = _rpgrtl_request_timeout
        data = json.dumps(payload).encode("utf-8")
        req = urllib2.Request(_rpgrtl_live_server + endpoint, data, {"Content-Type": "application/json"})
        return json.loads(urllib2.urlopen(req, timeout=timeout).read().decode("utf-8"))

    def _rpgrtl_log(event, payload=None):
        try:
            if payload is None:
                payload = {}
            payload["bridge_version"] = _rpgrtl_bridge_version
            payload["pid"] = os.getpid()
            _rpgrtl_send("/log", {"event": event, "payload": payload}, timeout=0.5)
        except Exception:
            pass

    def _rpgrtl_tagless(text):
        try:
            return re.sub(r"\{[^}]*\}", "", text).strip()
        except Exception:
            return text.strip() if isinstance(text, string_types) else ""

    def _rpgrtl_is_translatable(text):
        if not isinstance(text, string_types):
            return False
        cached = _rpgrtl_translatable_cache.get(text)
        if cached is not None:
            return cached
        clean = _rpgrtl_tagless(text).strip()
        if len(clean) <= 1:
            _rpgrtl_translatable_cache[text] = False
            return False
        if clean.startswith("[") and clean.endswith("]"):
            _rpgrtl_translatable_cache[text] = False
            return False
        for ch in clean:
            if "a" <= ch.lower() <= "z":
                _rpgrtl_translatable_cache[text] = True
                return True
            if "぀" <= ch <= "ヿ":
                _rpgrtl_translatable_cache[text] = True
                return True
            if "一" <= ch <= "鿿":
                _rpgrtl_translatable_cache[text] = True
                return True
        _rpgrtl_translatable_cache[text] = False
        return False

    def _rpgrtl_has_cjk(text):
        """Check if text contains any CJK characters (needs CJK font to render)."""
        if not isinstance(text, string_types):
            return False
        for ch in text:
            if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" or "豈" <= ch <= "﫿":
                return True
        return False

    def _rpgrtl_candidates(source):
        result = []
        seen = set()
        for value in (source,):
            if not isinstance(value, string_types):
                continue
            variants = [value, value.strip(), _rpgrtl_tagless(value), re.sub(r"\s+", " ", value.strip())]
            stripped = value.strip()
            if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
                variants.append(stripped[1:-1])
            for item in variants:
                if item and item not in seen:
                    seen.add(item)
                    result.append(item)
        return result

    def _rpgrtl_lookup(text):
        if not isinstance(text, string_types) or not text.strip():
            return None
        translations = _rpgrtl_translation_cache or _rpgrtl_local_cache
        if not translations:
            return None
        for key in _rpgrtl_candidates(text):
            if key in translations:
                return translations[key]
        return None

    def _rpgrtl_restart_interaction(reason="refresh"):
        global _rpgrtl_last_restart_interaction
        now = time.time()
        if now - _rpgrtl_last_restart_interaction < _rpgrtl_restart_interval:
            return False
        _rpgrtl_last_restart_interaction = now
        try:
            renpy.restart_interaction()
            return True
        except Exception:
            pass
        return False

    def _rpgrtl_load_local_cache():
        global _rpgrtl_local_cache
        try:
            if os.path.isfile(_rpgrtl_local_cache_file):
                with open(_rpgrtl_local_cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if (hasattr(data, "get") and hasattr(data, "keys")):
                    cached = data.get("translations", {})
                    if (hasattr(cached, "get") and hasattr(cached, "keys")):
                        _rpgrtl_local_cache = cached
                        _rpgrtl_log("local_cache_loaded", {"count": len(cached)})
        except Exception:
            pass

    def _rpgrtl_pull_translations():
        global _rpgrtl_translation_cache
        try:
            payload = _rpgrtl_send("/pull", {"pid": os.getpid()}, timeout=3.0)
            if (hasattr(payload, "get") and hasattr(payload, "keys")):
                translations = payload.get("translations", {})
                if (hasattr(translations, "get") and hasattr(translations, "keys")):
                    _rpgrtl_translation_cache = translations
                    _rpgrtl_local_cache.update(translations)
                    _rpgrtl_log("pull_success", {"count": len(translations)})
        except Exception:
            pass

    _rpgrtl_seen_queued = set()  # deduplicate pending_seen

    def _rpgrtl_report_seen(source, displayed, target, kind):
        key = source.strip() if isinstance(source, str) else ""
        if key and key in _rpgrtl_seen_queued:
            return
        if key:
            _rpgrtl_seen_queued.add(key)
        # Limit queue size to prevent memory leak
        if len(_rpgrtl_pending_seen) > 200:
            _rpgrtl_pending_seen[:] = _rpgrtl_pending_seen[-100:]
        _rpgrtl_pending_seen.append({"event": kind, "what": source, "displayed": displayed, "target": target or "", "matched": bool(target)})
        if len(_rpgrtl_seen_queued) > 5000:
            _rpgrtl_seen_queued.clear()

    def _rpgrtl_take_force_text(expected_source=None):
        global _rpgrtl_force_text
        forced = _rpgrtl_force_text
        if not forced:
            return ""
        if expected_source and not _rpgrtl_is_translatable(expected_source):
            return ""
        _rpgrtl_force_text = ""
        return forced

    def _rpgrtl_remember_active_widget(widget, source):
        global _rpgrtl_active_widget, _rpgrtl_active_source
        if widget is not None and source and _rpgrtl_is_translatable(source):
            _rpgrtl_active_widget = widget
            _rpgrtl_active_source = source

    def _rpgrtl_patch_active_widget(reason="translation_ready", forced_text=None):
        widget = _rpgrtl_active_widget
        source = _rpgrtl_active_source
        translated = forced_text if forced_text else _rpgrtl_lookup(source)
        _rpgrtl_debug("patch_active: widget=" + repr(type(widget).__name__ if widget else None) + " source=" + repr((source or "")[:40]) + " translated=" + repr((translated or "")[:40]) + " reason=" + reason)
        if not widget and not translated:
            return False
        if not translated:
            return False
        patched = False
        if widget is not None:
            try:
                if _rpgrtl_old_set_text:
                    _rpgrtl_old_set_text(widget, translated, None, False, True)
                else:
                    widget.text = [translated]
                _rpgrtl_log("active_widget_patched", {"source": (source or "")[:180], "target": translated[:180], "reason": reason})
                _rpgrtl_debug("patch_active SUCCESS: target=" + repr(translated[:60]))
                patched = True
            except Exception as exc:
                _rpgrtl_log("active_widget_patch_failed", {"source": (source or "")[:180], "error": str(exc), "reason": reason})
                _rpgrtl_debug("patch_active FAILED: " + repr(exc))
        try:
            for w in renpy.display.screen.current_screen().children if hasattr(renpy.display.screen, "current_screen") and callable(renpy.display.screen.current_screen) else []:
                if hasattr(w, "text"):
                    if _rpgrtl_old_set_text:
                        _rpgrtl_old_set_text(w, translated, None, False, True)
                    else:
                        w.text = [translated]
                    patched = True
        except Exception:
            pass
        if patched:
            try:
                renpy.restart_interaction()
            except Exception:
                pass
        return patched

    # Direct widget update: find Text widget with id="what" via screen API
    # and call set_text() on it. Does NOT restart interaction.
    def _rpgrtl_force_update_current_text(forced_text):
        _rpgrtl_debug("force_update_current_text: " + repr(forced_text[:60]))
        updated = False
        try:
            # Try renpy.display.screen.get_screen("say") to get the say screen
            say_screen = None
            try:
                say_screen = renpy.display.screen.get_screen("say")
            except Exception:
                pass
            if say_screen is None:
                # Fallback: try current_screen
                try:
                    if hasattr(renpy.display.screen, "current_screen") and callable(renpy.display.screen.current_screen):
                        say_screen = renpy.display.screen.current_screen()
                except Exception:
                    pass
            if say_screen is not None:
                # Find the "what" widget by traversing children
                def find_what_widget(obj, depth=0):
                    if depth > 20:
                        return None
                    # Check if this object has the id "what"
                    if hasattr(obj, "widget_id") and obj.widget_id == "what":
                        return obj
                    if hasattr(obj, "id") and obj.id == "what" and hasattr(obj, "text"):
                        return obj
                    # Check children
                    if hasattr(obj, "children"):
                        for child in obj.children:
                            result = find_what_widget(child, depth + 1)
                            if result:
                                return result
                    if hasattr(obj, "child"):
                        result = find_what_widget(obj.child, depth + 1)
                        if result:
                            return result
                    if hasattr(obj, "content"):
                        result = find_what_widget(obj.content, depth + 1)
                        if result:
                            return result
                    return None
                widget = find_what_widget(say_screen)
                if widget is not None:
                    _rpgrtl_debug("force_update: found widget " + repr(type(widget).__name__))
                    if _rpgrtl_old_set_text:
                        _rpgrtl_old_set_text(widget, forced_text, None, False, True)
                    else:
                        widget.text = [forced_text]
                    _rpgrtl_debug("force_update: set_text done")
                    updated = True
                    # set_text invalidates the render cache; the event loop will
                    # re-render the screen on the next draw cycle automatically.
                    # Do NOT call restart_interaction — it ends the current interaction
                    # and causes the dialogue to advance to the next line.
                else:
                    _rpgrtl_debug("force_update: 'what' widget not found in screen tree")
            else:
                _rpgrtl_debug("force_update: no screen found")
        except Exception as exc:
            _rpgrtl_debug("force_update EXCEPTION: " + repr(exc))
        return updated

    # Force-update choice buttons on the "choice" screen when translations arrive late.
    # With the Text.render hook now active, this is mostly a backup mechanism.
    def _rpgrtl_force_update_choice_buttons():
        """Patch choice screen buttons with translated text if available."""
        try:
            choice_screen = renpy.display.screen.get_screen("choice")
            if choice_screen is None:
                return False

            def find_all_text_widgets(obj, depth=0):
                """Find all Text widgets in the screen tree."""
                if depth > 30:
                    return []
                results = []
                cls_name = type(obj).__name__
                if hasattr(obj, "text") and isinstance(obj.text, list) and cls_name == "Text":
                    results.append(obj)
                if hasattr(obj, "children"):
                    for child in obj.children:
                        results.extend(find_all_text_widgets(child, depth + 1))
                if hasattr(obj, "child"):
                    results.extend(find_all_text_widgets(obj.child, depth + 1))
                if hasattr(obj, "content"):
                    results.extend(find_all_text_widgets(obj.content, depth + 1))
                return results

            widgets = find_all_text_widgets(choice_screen)
            updated = False
            for widget in widgets:
                current_text = widget.text
                if isinstance(current_text, list) and len(current_text) == 1:
                    txt = current_text[0]
                    if isinstance(txt, str) and txt.strip():
                        translated = _rpgrtl_lookup(txt)
                        if translated and translated != txt:
                            if _rpgrtl_cjk_font:
                                translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
                            widget.text = [translated]
                            _rpgrtl_text_modified[id(widget)] = translated
                            updated = True
                            _rpgrtl_debug("choice_widget_patched: " + repr(txt[:40]) + " -> " + repr(translated[:40]))
            if updated:
                import pygame
                pygame.event.post(pygame.event.Event(25))  # PERIODIC event
            return updated
        except Exception as exc:
            _rpgrtl_debug("force_update_choice EXCEPTION: " + repr(exc))
            return False

    # Track whether a menu is currently active for live patching
    _rpgrtl_menu_active = [False]

    # Hook: Text.set_text (projz pattern - call old first, then self.text=[translated])
    _rpgrtl_old_set_text = None
    try:
        _rpgrtl_old_set_text = renpy.text.text.Text.set_text
    except Exception:
        pass

    def _rpgrtl_hook_set_text(self, text, scope=None, substitute=False, update=True):
        global _rpgrtl_active_widget, _rpgrtl_active_source, _rpgrtl_force_text
        res = _rpgrtl_old_set_text(self, text, scope, substitute, update) if _rpgrtl_old_set_text else None
        if not isinstance(text, (string_types, list)):
            return res
        old_text = None
        if isinstance(text, string_types):
            old_text = text
        elif len(text) == 1 and isinstance(text[0], string_types):
            old_text = text[0]
        if old_text and _rpgrtl_is_translatable(old_text):
            _rpgrtl_remember_active_widget(self, old_text)
            _rpgrtl_debug("set_text TRACK: widget=" + repr(type(self).__name__) + " text=" + repr(old_text[:60]))
        forced = _rpgrtl_force_text if isinstance(_rpgrtl_force_text, string_types) else ""
        if forced and old_text and _rpgrtl_is_translatable(old_text):
            _rpgrtl_debug("set_text FORCE: old_text=" + repr(old_text[:60]) + " forced=" + repr(forced[:60]))
            try:
                self.text = [forced]
                _rpgrtl_force_text = ""
                _rpgrtl_log("set_text_force_replace", {"source": old_text[:180], "target": forced[:180]})
                _rpgrtl_patch_active_widget("set_text_force")
                return True
            except Exception as exc:
                _rpgrtl_debug("set_text FORCE FAILED: " + repr(exc))
                _rpgrtl_log("set_text_force_failed", {"source": old_text[:180], "error": str(exc), "target": forced[:180]})
        if not old_text or not _rpgrtl_is_translatable(old_text):
            return res
        translated = _rpgrtl_lookup(old_text)
        if translated and translated != old_text:
            try:
                self.text = [translated]
                _rpgrtl_log("set_text_replace", {"source": old_text[:180], "target": translated[:180]})
                return True
            except Exception:
                pass
        return res

    # Hook: ADVCharacter.__call__ (track raw what for translate_identifier)
    _rpgrtl_old_character_call = None
    try:
        _rpgrtl_old_character_call = renpy.character.ADVCharacter.__call__
    except Exception:
        pass

    def _rpgrtl_hook_character_call(self, what, **kwargs):
        global _rpgrtl_tid_what
        try:
            _rpgrtl_tid_what = (renpy.game.context().translate_identifier, what)
        except Exception:
            _rpgrtl_tid_what = (None, what)
        return _rpgrtl_old_character_call(self, what, **kwargs)

    # Hook: ADVCharacter.prefix_suffix (projz pattern - return translated directly)
    _rpgrtl_old_prefix_suffix = None
    try:
        _rpgrtl_old_prefix_suffix = renpy.character.ADVCharacter.prefix_suffix
    except Exception:
        pass

    def _rpgrtl_hook_prefix_suffix(self, thing, prefix, body, suffix):
        global _rpgrtl_force_text, _rpgrtl_force_applied
        if _rpgrtl_old_prefix_suffix:
            res = _rpgrtl_old_prefix_suffix(self, thing, prefix, body, suffix)
        else:
            res = (prefix or "") + (body or "") + (suffix or "")
        if body is None or thing not in ("what", "who"):
            return res
        forced = _rpgrtl_force_text if isinstance(_rpgrtl_force_text, string_types) else ""
        if forced and thing == "what":
            _rpgrtl_debug("prefix_suffix FORCE: body=" + repr(body[:60]) + " forced=" + repr(forced[:60]))
            # Do NOT clear _rpgrtl_force_text here — let do_display handle it.
            # do_display will display the forced text and wait for player input.
            _rpgrtl_force_applied = True
            _rpgrtl_report_seen(body, res, forced, "force_text")
            _rpgrtl_log("prefix_suffix_force_replace", {"source": body[:180], "target": forced[:180]})
            return (prefix or "") + forced + (suffix or "")
        if not _rpgrtl_is_translatable(res):
            return res
        translated = _rpgrtl_lookup(body)
        if translated and translated != body:
            if _rpgrtl_cjk_font and _rpgrtl_has_cjk(translated):
                translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
            _rpgrtl_report_seen(body, res, translated, "prefix_suffix")
            try:
                result = _rpgrtl_old_prefix_suffix(self, thing, prefix, translated, suffix) if _rpgrtl_old_prefix_suffix else (prefix or "") + translated + (suffix or "")
                _rpgrtl_log("prefix_suffix_replace", {"source": body[:180], "target": translated[:180]})
                return result
            except Exception:
                return (prefix or "") + translated + (suffix or "")
        _rpgrtl_report_seen(body, res, "", "prefix_suffix")
        _rpgrtl_pending_lookup.add(body.strip())
        return res

    # Hook: ADVCharacter.do_display (projz pattern - replace who/what, handle DTT)
    _rpgrtl_old_do_display = None
    try:
        _rpgrtl_old_do_display = renpy.character.ADVCharacter.do_display
    except Exception:
        pass

    _rpgrtl_dialogue_text_tags = None
    try:
        _rpgrtl_dialogue_text_tags = renpy.character.DialogueTextTags
    except Exception:
        pass

    def _rpgrtl_hook_do_display(self, who, what, **display_args):
        global _rpgrtl_force_text, _rpgrtl_force_applied
        # Check force_text FIRST — this is the primary injection mechanism.
        # When restart_interaction re-enters do_display, force_text is set by prefix_suffix.
        forced = _rpgrtl_force_text if isinstance(_rpgrtl_force_text, string_types) else ""
        if forced:
            if _rpgrtl_cjk_font and _rpgrtl_has_cjk(forced):
                forced = "{font=" + _rpgrtl_cjk_font + "}" + forced + "{/font}"
            _rpgrtl_debug("do_display FORCE: forced=" + repr(forced[:60]) + " what=" + repr(what[:60]))
            _rpgrtl_force_text = ""
            _rpgrtl_force_applied = False
            _rpgrtl_report_seen(what, what, forced, "force_text")
            _rpgrtl_log("do_display_force_replace", {"source": what[:180], "target": forced[:180]})
            _rpgrtl_old_do_display(self, who, forced, **display_args)
            return
        if _rpgrtl_force_applied:
            _rpgrtl_force_applied = False
            try:
                _rpgrtl_old_do_display(self, who, what, **display_args)
            except Exception:
                pass
            return
        new_what = what
        try:
            context_tid = renpy.game.context().translate_identifier
        except Exception:
            context_tid = None
        tid, raw_what = _rpgrtl_tid_what
        source_what = raw_what if tid == context_tid and isinstance(raw_what, string_types) else what
        forced = _rpgrtl_force_text if isinstance(_rpgrtl_force_text, string_types) else ""
        if forced and source_what:
            _rpgrtl_debug("do_display FORCE: source=" + repr(source_what[:60]) + " forced=" + repr(forced[:60]))
            new_what = forced
            _rpgrtl_force_text = ""
            translated = forced
            _rpgrtl_report_seen(source_what, what, translated, "force_text")
            _rpgrtl_log("do_display_force_replace", {"source": source_what[:180], "target": translated[:180]})
            try:
                _rpgrtl_old_do_display(self, who, forced, **display_args)
            except Exception:
                pass
            return
        else:
            translated = _rpgrtl_lookup(source_what)
            if not translated and source_what != what:
                translated = _rpgrtl_lookup(what)
            if translated:
                new_what = translated
                _rpgrtl_report_seen(source_what, what, translated, "do_display")
                _rpgrtl_log("do_display_replace", {"source": source_what[:180], "target": translated[:180]})
            else:
                _rpgrtl_report_seen(source_what, what, "", "do_display")
                _rpgrtl_pending_lookup.add(source_what.strip())
        new_who = who
        if isinstance(who, string_types):
            who_translated = _rpgrtl_lookup(who)
            if who_translated:
                new_who = who_translated
        old_dtt = display_args.get("dtt", None)
        new_dtt = None
        if translated and _rpgrtl_dialogue_text_tags and old_dtt is not None:
            try:
                new_dtt = _rpgrtl_dialogue_text_tags(new_what)
                display_args["dtt"] = new_dtt
            except Exception:
                new_dtt = None
        _rpgrtl_old_do_display(self, new_who, new_what, **display_args)
        if new_dtt is not None and old_dtt is not None:
            try:
                for k, v in vars(new_dtt).items():
                    setattr(old_dtt, k, v)
                display_args["dtt"] = old_dtt
            except Exception:
                pass

    # Hook: Menu.execute — translate menu choice labels before display
    _rpgrtl_old_Menu_execute = None
    try:
        _rpgrtl_old_Menu_execute = renpy.ast.Menu.execute
    except Exception:
        pass

    def _rpgrtl_hook_Menu_execute(self):
        # Translate choice labels in-place before the menu is displayed
        try:
            items = getattr(self, 'items', None)
            if items and isinstance(items, list):
                changed = False
                for i, item in enumerate(items):
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        label = item[0]
                        if isinstance(label, str) and label.strip():
                            translated = _rpgrtl_lookup(label)
                            if translated and translated != label:
                                if _rpgrtl_cjk_font:
                                    translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
                                new_item = (translated,) + tuple(item[1:])
                                items[i] = new_item
                                changed = True
                                _rpgrtl_report_seen(label, label, translated, "menu_choice")
                                _rpgrtl_log("menu_choice_replace", {"source": label[:180], "target": translated[:180]})
                            else:
                                _rpgrtl_pending_lookup.add(label.strip())
        except Exception as exc:
            _rpgrtl_debug("menu_choice translate error: " + repr(exc))
        if _rpgrtl_old_Menu_execute:
            _rpgrtl_menu_active[0] = True
            try:
                return _rpgrtl_old_Menu_execute(self)
            finally:
                _rpgrtl_menu_active[0] = False

    # Hook: renpy.display_menu — translate choice labels right before screen display
    _rpgrtl_old_display_menu = None
    try:
        _rpgrtl_old_display_menu = renpy.display_menu
    except Exception:
        pass

    def _rpgrtl_hook_display_menu(items, *args, **kwargs):
        # Translate labels in the items list before passing to original display_menu
        if isinstance(items, list):
            new_items = []
            for item in items:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    label = item[0]
                    if isinstance(label, str) and label.strip():
                        translated = _rpgrtl_lookup(label)
                        if translated and translated != label:
                            if _rpgrtl_cjk_font:
                                translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
                            _rpgrtl_debug("display_menu translate: " + repr(label[:40]) + " -> " + repr(translated[:40]))
                            new_items.append((translated,) + tuple(item[1:]))
                            continue
                new_items.append(item)
            items = new_items
        if _rpgrtl_old_display_menu:
            return _rpgrtl_old_display_menu(items, *args, **kwargs)

    # Install hooks
    try:
        if _rpgrtl_old_character_call:
            renpy.character.ADVCharacter.__call__ = _rpgrtl_hook_character_call
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook character_call failed:", e)
    try:
        if _rpgrtl_old_prefix_suffix:
            renpy.character.ADVCharacter.prefix_suffix = _rpgrtl_hook_prefix_suffix
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook prefix_suffix failed:", e)
    try:
        if _rpgrtl_old_do_display:
            renpy.character.ADVCharacter.do_display = _rpgrtl_hook_do_display
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook do_display failed:", e)
    try:
        if _rpgrtl_old_set_text:
            renpy.text.text.Text.set_text = _rpgrtl_hook_set_text
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook Text.set_text failed:", e)
    try:
        if _rpgrtl_old_Menu_execute:
            renpy.ast.Menu.execute = _rpgrtl_hook_Menu_execute
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook Menu.execute failed:", e)
    try:
        if _rpgrtl_old_display_menu:
            renpy.display_menu = _rpgrtl_hook_display_menu
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook display_menu failed:", e)

    # Startup verification: log which hooks were installed
    _rpgrtl_debug("HOOK STATUS: character_call=" + str(_rpgrtl_old_character_call is not None) +
                  " prefix_suffix=" + str(_rpgrtl_old_prefix_suffix is not None) +
                  " do_display=" + str(_rpgrtl_old_do_display is not None) +
                  " set_text=" + str(_rpgrtl_old_set_text is not None) +
                  " Menu.execute=" + str(_rpgrtl_old_Menu_execute is not None) +
                  " display_menu=" + str(_rpgrtl_old_display_menu is not None))
    _rpgrtl_debug("CJK FONT: " + repr(_rpgrtl_cjk_font) + " cache_count=" + str(len(_rpgrtl_local_cache)) + " trans_cache=" + str(len(_rpgrtl_translation_cache)))
    try:
        _def_font = getattr(config, 'default_font', None)
        _gui_font = getattr(gui, 'text_font', None) if 'gui' in dir() else None
        _rpgrtl_debug("FONTS: config.default_font=" + repr(_def_font) + " gui.text_font=" + repr(_gui_font))
    except Exception:
        pass

    # config.say_menu_text_filter: translate menu labels during Menu.execute
    _rpgrtl_prev_menu_filter = getattr(config, "say_menu_text_filter", None)
    def _rpgrtl_menu_text_filter(label):
        if _rpgrtl_prev_menu_filter:
            label = _rpgrtl_prev_menu_filter(label)
        if isinstance(label, str) and label.strip():
            _rpgrtl_debug("menu_filter: " + repr(label[:60]))
            translated = _rpgrtl_lookup(label)
            if translated and translated != label:
                if _rpgrtl_cjk_font:
                    translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
                _rpgrtl_debug("menu_filter REPLACE: " + repr(label[:40]) + " -> " + repr(translated[:40]))
                _rpgrtl_log("menu_filter_replace", {"source": label[:180], "target": translated[:180]})
                return translated
        return label
    config.say_menu_text_filter = _rpgrtl_menu_text_filter

    # config.replace_text: intercept ALL text at render time
    _rpgrtl_config_prev_replace = getattr(config, "replace_text", None)
    def _rpgrtl_config_replace_text(s):
        if not isinstance(s, string_types):
            return s
        if _rpgrtl_config_prev_replace is not None:
            return _rpgrtl_config_prev_replace(s)
        return s
    config.replace_text = _rpgrtl_config_replace_text

    # Text.render() hook: intercept ALL text at render time and apply cached translations.
    # This is the primary injection mechanism — works for dialogue AND choice buttons.
    # self.text is a LIST in Ren'Py, not a string.
    _rpgrtl_text_modified = {}  # {id(widget): translated_text} — tracks widgets we've modified
    _rpgrtl_force_apply_count = 0
    _rpgrtl_render_apply_count = 0
    _rpgrtl_render_diag_until = time.time() + 30  # log all text for first 30 seconds
    _rpgrtl_render_diag_count = 0
    try:
        _rpgrtl_Text_cls = renpy.text.text.Text
        _rpgrtl_orig_Text_render = _rpgrtl_Text_cls.render
        def _rpgrtl_hook_Text_render(self, width, height, st, at):
            global _rpgrtl_force_text, _rpgrtl_force_apply_count, _rpgrtl_render_apply_count
            global _rpgrtl_active_widget, _rpgrtl_active_source, _rpgrtl_render_diag_count
            forced = _rpgrtl_force_text
            wid = id(self)
            # --- Force text injection (manual "hello" test) ---
            if forced and isinstance(forced, string_types):
                if wid not in _rpgrtl_text_modified:
                    _rpgrtl_force_apply_count += 1
                    _rpgrtl_debug("Text.render FORCE apply: " + repr(forced[:60]) + " count=" + str(_rpgrtl_force_apply_count))
                _rpgrtl_text_modified[wid] = forced
                self.text = [forced]
                result = _rpgrtl_orig_Text_render(self, width, height, st, at + 0.001)
                if _rpgrtl_force_apply_count >= 1:
                    _rpgrtl_force_text = ""
                    _rpgrtl_force_apply_count = 0
                return result
            # --- Diagnostic: log ALL translatable text for first 30 seconds ---
            if time.time() < _rpgrtl_render_diag_until:
                try:
                    _ctl = self.text
                    if isinstance(_ctl, list) and len(_ctl) >= 1 and isinstance(_ctl[0], string_types) and _ctl[0].strip():
                        _raw = _ctl[0]
                        if _rpgrtl_is_translatable(_raw):
                            _rpgrtl_render_diag_count += 1
                            if _rpgrtl_render_diag_count <= 50:
                                _sty = ""
                                try:
                                    _sty = getattr(self, 'style', None)
                                    _sty = getattr(_sty, 'name', '') if _sty else ''
                                except Exception:
                                    pass
                                _rpgrtl_debug("render_diag: style=" + repr(_sty) + " text=" + repr(_raw[:80]))
                except Exception:
                    pass
            # --- Cached translation injection (primary mechanism) ---
            try:
                current_text_list = self.text
                if isinstance(current_text_list, list) and len(current_text_list) >= 1:
                    raw = current_text_list[0]
                    if isinstance(raw, string_types) and raw.strip() and _rpgrtl_is_translatable(raw):
                        # If already translated (self.text was set to translated), skip
                        prev_translated = _rpgrtl_text_modified.get(wid)
                        if prev_translated and isinstance(prev_translated, string_types) and raw == prev_translated:
                            # Already translated — just track and render
                            _rpgrtl_active_widget = self
                            _rpgrtl_active_source = raw
                            return _rpgrtl_orig_Text_render(self, width, height, st, at)
                        # New or changed text — clear stale tracking
                        if prev_translated is not None and prev_translated != raw:
                            _rpgrtl_text_modified.pop(wid, None)
                        # Remember this widget for live patching
                        _rpgrtl_active_widget = self
                        _rpgrtl_active_source = raw
                        # Queue for translation if not cached
                        if raw not in _rpgrtl_translation_cache:
                            _rpgrtl_pending_lookup.add(raw.strip())
                        translated = _rpgrtl_lookup(raw)
                        if translated and translated != raw:
                            if _rpgrtl_cjk_font:
                                translated = "{font=" + _rpgrtl_cjk_font + "}" + translated + "{/font}"
                            _rpgrtl_text_modified[wid] = translated
                            self.text = [translated]
                            _rpgrtl_render_apply_count += 1
                            if _rpgrtl_render_apply_count <= 10:
                                _rpgrtl_debug("Text.render CACHE apply: " + repr(raw[:50]) + " -> " + repr(translated[:50]))
                            result = _rpgrtl_orig_Text_render(self, width, height, st, at + 0.001)
                            return result
                        # Text has CJK chars (already translated by menu_filter etc) but
                        # no cache hit — apply {font} tag so CJK glyphs render correctly
                        if _rpgrtl_cjk_font and _rpgrtl_has_cjk(raw) and not raw.startswith("{font="):
                            font_text = "{font=" + _rpgrtl_cjk_font + "}" + raw + "{/font}"
                            _rpgrtl_text_modified[wid] = font_text
                            self.text = [font_text]
                            result = _rpgrtl_orig_Text_render(self, width, height, st, at + 0.001)
                            return result
            except Exception:
                pass
            return _rpgrtl_orig_Text_render(self, width, height, st, at)
        _rpgrtl_Text_cls.render = _rpgrtl_hook_Text_render
        _rpgrtl_debug("Hooked Text.render")
    except Exception as e:
        print("[RPGRenPyLocalizer] Hook Text.render failed:", e)

    # Load cache + pull from server
    _rpgrtl_load_local_cache()
    try:
        _rpgrtl_pull_translations()
    except Exception:
        pass

    # AST lookahead: extract upcoming dialogue/choices for pre-translation
    _rpgrtl_last_lookahead_node = [None]
    _rpgrtl_lookahead_interval = 5.0
    def _rpgrtl_lookahead_texts():
        """Traverse upcoming AST nodes to extract dialogue and choice texts."""
        try:
            ctx = renpy.game.context()
            current_name = ctx.current
            # Only re-scan if we moved to a new node
            if current_name == _rpgrtl_last_lookahead_node[0]:
                return []
            _rpgrtl_last_lookahead_node[0] = current_name
            current = renpy.game.script.lookup(current_name)
            if current is None:
                return []
        except Exception:
            return []
        results = []
        visited = set()
        queue = []
        # Start from the NEXT node (not current, which is already displayed)
        if current.next:
            queue.append(current.next)
        while queue and len(results) < 200:
            node = queue.pop(0)
            if node is None:
                continue
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            try:
                if hasattr(node, 'what') and hasattr(node, 'who'):
                    # Say node — extract dialogue text
                    what = getattr(node, 'what', None)
                    if isinstance(what, str) and what.strip():
                        results.append(what)
                elif hasattr(node, 'items') and hasattr(node, 'has_caption'):
                    # Menu node — extract choice labels
                    items = getattr(node, 'items', [])
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) >= 1:
                            label = item[0]
                            if isinstance(label, str) and label.strip():
                                results.append(label)
                # Traverse linear next
                nxt = getattr(node, 'next', None)
                if nxt is not None and id(nxt) not in visited:
                    queue.append(nxt)
                # Explore If branches
                entries = getattr(node, 'entries', None)
                if entries and isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                            block = entry[1]
                            if isinstance(block, list) and block:
                                queue.append(block[0])
                # Explore Menu choice branches
                items = getattr(node, 'items', None)
                if items and isinstance(items, list) and hasattr(node, 'has_caption'):
                    for item in items:
                        if isinstance(item, (list, tuple)) and len(item) >= 3:
                            block = item[2]
                            if isinstance(block, list) and block:
                                queue.append(block[0])
            except Exception:
                continue
        return results

    # Background thread: poll for new translations
    def _rpgrtl_background_update():
        _rpgrtl_last_pull_time = [0.0]
        _rpgrtl_last_lookahead_time = [0.0]
        def _update_loop():
            global _rpgrtl_last_notify_seq, _rpgrtl_active_widget, _rpgrtl_active_source, _rpgrtl_force_text
            while True:
                try:
                    time.sleep(_rpgrtl_bg_loop_interval)
                    now = time.time()
                    # Periodic pull: every 1 second, refresh full translation table from server
                    if now - _rpgrtl_last_pull_time[0] >= 2.0:
                        _rpgrtl_last_pull_time[0] = now
                        old_count = len(_rpgrtl_translation_cache)
                        _rpgrtl_pull_translations()
                        new_count = len(_rpgrtl_translation_cache)
                        if new_count > old_count and old_count == 0:
                            _rpgrtl_restart_interaction("cache_warmed")
                    # AST lookahead: every 5 seconds, send upcoming texts for pre-translation
                    if now - _rpgrtl_last_lookahead_time[0] >= _rpgrtl_lookahead_interval:
                        _rpgrtl_last_lookahead_time[0] = now
                        try:
                            upcoming = _rpgrtl_lookahead_texts()
                            if upcoming:
                                # Filter out already-translated texts
                                to_send = [t for t in upcoming if t not in _rpgrtl_translation_cache]
                                if to_send:
                                    payload = _rpgrtl_send("/pre_translate", {"texts": to_send[:50]}, timeout=1.0)
                                    if hasattr(payload, "get") and hasattr(payload, "keys"):
                                        trans = payload.get("translations", {})
                                        if hasattr(trans, "items"):
                                            for src, tgt in trans.items():
                                                if src and tgt:
                                                    _rpgrtl_translation_cache[src] = tgt
                                                    _rpgrtl_local_cache[src] = tgt
                                    _rpgrtl_debug("lookahead: " + str(len(upcoming)) + " upcoming, " + str(len(to_send)) + " sent")
                        except Exception as _la_exc:
                            _rpgrtl_debug("lookahead EXCEPTION: " + repr(_la_exc))
                    new_translations = {}
                    # Batch /seen: send all pending seen events in ONE HTTP call
                    batch = []
                    while _rpgrtl_pending_seen:
                        try:
                            batch.append(_rpgrtl_pending_seen.pop(0))
                        except IndexError:
                            break
                    if batch:
                        try:
                            payload = _rpgrtl_send("/seen_batch", {"items": batch[:50]}, timeout=1.0)
                            if hasattr(payload, "get") and hasattr(payload, "keys"):
                                targets = payload.get("targets", [])
                                for i, event in enumerate(batch[:50]):
                                    if i < len(targets):
                                        target = str(targets[i] or "")
                                        source = str(event.get("what", "") or "")
                                        if target and source:
                                            _rpgrtl_translation_cache[source] = target
                                            _rpgrtl_local_cache[source] = target
                                            new_translations[source] = target
                        except Exception:
                            for event in batch:
                                _rpgrtl_pending_seen.append(event)
                    # Batch /translation: send all pending lookups in ONE HTTP call
                    lookups = list(_rpgrtl_pending_lookup)
                    _rpgrtl_pending_lookup.clear()
                    if lookups:
                        try:
                            payload = _rpgrtl_send("/translation_batch", {"texts": lookups[:30]}, timeout=1.0)
                            if hasattr(payload, "get") and hasattr(payload, "keys"):
                                trans = payload.get("translations", {})
                                if hasattr(trans, "items"):
                                    for src, tgt in trans.items():
                                        if src and tgt:
                                            _rpgrtl_translation_cache[src] = tgt
                                            _rpgrtl_local_cache[src] = tgt
                                            new_translations[src] = tgt
                        except Exception:
                            pass
                        # Re-add texts that weren't found
                        for text in lookups:
                            if text not in _rpgrtl_translation_cache:
                                _rpgrtl_pending_lookup.add(text)
                    # Proactively request translation for current active source
                    active_src = _rpgrtl_active_source
                    if active_src and active_src.strip() and active_src not in _rpgrtl_translation_cache:
                        _rpgrtl_pending_lookup.add(active_src.strip())
                    # Patch active widget if translation just arrived — use the working
                    # injection method (screen.widgets + set_text + pygame event)
                    if active_src and _rpgrtl_is_translatable(active_src):
                        translated = _rpgrtl_lookup(active_src)
                        if translated and translated != active_src:
                            _rpgrtl_debug("active_src has translation: " + repr(active_src[:40]) + " -> " + repr(translated[:40]))
                            _rpgrtl_force_update_current_text(translated)
                    # If new translations arrived and a menu is active, patch choice buttons
                    if new_translations and _rpgrtl_menu_active[0]:
                        try:
                            _rpgrtl_force_update_choice_buttons()
                        except Exception:
                            pass
                    try:
                        notify_payload = _rpgrtl_send("/notify", {}, timeout=0.3)
                        if hasattr(notify_payload, "get") and hasattr(notify_payload, "keys"):
                            server_seq = int(notify_payload.get("seq", 0))
                            force_text = str(notify_payload.get("force_text", "") or "")
                            _rpgrtl_debug("notify parsed: seq=" + str(server_seq) + " force_text=" + repr(force_text[:60]) + " last_seq=" + str(_rpgrtl_last_notify_seq))
                            if server_seq > _rpgrtl_last_notify_seq:
                                _rpgrtl_last_notify_seq = server_seq
                                _rpgrtl_pull_translations()
                            if force_text:
                                _rpgrtl_force_text = force_text
                                _rpgrtl_debug("notify FORCE_TEXT received: " + repr(force_text[:100]))
                                _rpgrtl_log("force_text_received", {"target": force_text[:180]})
                                # Directly update the Text widget via screen API.
                                # Does NOT restart interaction (which would advance dialogue).
                                _rpgrtl_force_update_current_text(force_text)
                                _rpgrtl_force_text = ""
                            else:
                                _rpgrtl_patch_active_widget("notify_refresh")
                                _rpgrtl_restart_interaction("notify_refresh")
                        else:
                            _rpgrtl_debug("notify response not dict: " + repr(type(notify_payload)))
                    except Exception as _notify_exc:
                        _rpgrtl_debug("notify EXCEPTION: " + repr(_notify_exc))
                except Exception as _loop_exc:
                    _rpgrtl_debug("loop EXCEPTION: " + repr(_loop_exc))
                # Flush buffered log periodically
                try:
                    with _LIVE_LOG_LOCK:
                        if _LIVE_LOG_BUFFER and time.time() - _LIVE_LOG_LAST_FLUSH >= 3.0:
                            _flush_live_log_buffer()
                except Exception:
                    pass
        threading.Thread(target=_update_loop, daemon=True).start()

    try:
        _rpgrtl_background_update()
    except Exception:
        pass

    # Boot log
    try:
        _rpgrtl_log("bridge_loaded", {"version": _rpgrtl_bridge_version, "gamedir": config.gamedir, "cache_count": len(_rpgrtl_translation_cache)})
        _rpgrtl_send("/boot", {"pid": os.getpid(), "root": config.gamedir, "version": renpy.version_only + " bridge " + _rpgrtl_bridge_version})
    except Exception:
        pass
'''


class RenPyService:
    def __init__(self, project: ProjectInfo) -> None:
        if not project.scripts_dir:
            raise ValueError("Ren'Py 项目缺少 game 脚本目录。")
        self.project = project
        self.scripts_dir = project.scripts_dir

    def extract_translations(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        entries.extend(self._extract_from_translation_files())
        entries.extend(self._extract_from_runtime_cache())
        for file_path in sorted(self._candidate_files()):
            if self._is_translation_file(file_path):
                entries.extend(self._extract_from_translation_file(file_path))
            else:
                entries.extend(self._extract_from_script_file(file_path))
        return self._deduplicate(entries)

    def _extract_from_translation_files(self) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        tl_root = self.scripts_dir / "tl"
        if not tl_root.exists():
            return entries
        for file_path in sorted(tl_root.rglob("*.rpy")):
            if self._is_generated_file(file_path):
                continue
            entries.extend(self._extract_from_translation_file(file_path))
        return entries

    def runtime_export_path(self) -> Path:
        return self.project.root / ".rpgrtl_workspace" / "renpy_extracted.json"

    def install_runtime_extractor(self, clear_cache: bool = False) -> Path:
        path = self.scripts_dir / EXTRACTOR_NAME
        path.write_text(RENPLY_RUNTIME_EXTRACTOR_SOURCE.strip() + "\n", encoding="utf-8", newline="\n")
        if clear_cache:
            try:
                self.runtime_export_path().unlink()
            except FileNotFoundError:
                pass
        return path

    def install_live_translation_bridge(self, clear_seen: bool = False) -> Path:
        self.start_live_bridge_server(clear_events=clear_seen)
        path = self.scripts_dir / LIVE_BRIDGE_NAME
        source = RENPY_LIVE_BRIDGE_SOURCE.replace("__RPGRTL_PORT__", str(LIVE_BRIDGE_PORT)).replace("__RPGRTL_BRIDGE_VERSION__", LIVE_BRIDGE_VERSION)
        path.write_text(source.strip() + "\n", encoding="utf-8", newline="\n")
        _append_live_log("tool", "install_live_translation_bridge", {"path": str(path), "version": LIVE_BRIDGE_VERSION, "clear_seen": clear_seen})
        try:
            path.with_suffix(".rpyc").unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            _append_live_log("tool", "rpyc_delete_failed", {"path": str(path.with_suffix('.rpyc')), "error": str(exc)})
        workspace = self.project.root / ".rpgrtl_workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        if clear_seen:
            try:
                (workspace / LIVE_SEEN_NAME).unlink()
            except FileNotFoundError:
                pass
        return path

    def start_live_bridge_server(self, clear_events: bool = False) -> None:
        global _LIVE_SERVER
        with _LIVE_SERVER_LOCK:
            if clear_events:
                _LIVE_SERVER_STATE["events"] = []
                _LIVE_SERVER_STATE["seen"] = {}
                _LIVE_SERVER_STATE["translations"] = {}
                _LIVE_SERVER_STATE["force_text"] = ""
            if _LIVE_SERVER is not None:
                _append_live_log("tool", "live_bridge_server_reuse", {"port": LIVE_BRIDGE_PORT, "clear_events": clear_events})
                return
            try:
                _LIVE_SERVER = ThreadingHTTPServer(("127.0.0.1", LIVE_BRIDGE_PORT), _RenPyLiveBridgeHandler)
            except OSError as exc:
                _LIVE_SERVER = None
                raise RuntimeError(f"本地 Ren'Py 实时桥接端口 {LIVE_BRIDGE_PORT} 被占用或无法启动：{exc}") from exc
            thread = threading.Thread(target=_LIVE_SERVER.serve_forever, daemon=True)
            thread.start()
            _append_live_log("tool", "live_bridge_server_started", {"port": LIVE_BRIDGE_PORT})

    def live_translation_path(self) -> Path:
        return self.project.root / ".rpgrtl_workspace" / LIVE_TRANSLATIONS_NAME

    def live_seen_path(self) -> Path:
        return self.project.root / ".rpgrtl_workspace" / LIVE_SEEN_NAME

    def write_live_translation_table(self, translations: dict[str, TranslationEntry]) -> tuple[Path, int]:
        entries = self._safe_translation_entries(translations.values())
        mapping: dict[str, str] = {}
        for entry in entries:
            target = self._sanitize_renpy_text(entry.source, entry.target)
            mapping[entry.source] = target
            for candidate in _live_translation_candidates(entry.source):
                mapping.setdefault(candidate, target)
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE["translations"] = dict(mapping)
        workspace = self.project.root / ".rpgrtl_workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        output = workspace / LIVE_TRANSLATIONS_NAME
        payload = {
            "version": 1,
            "updated_at": time.time(),
            "translations": mapping,
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        _append_live_log("tool", "write_live_translation_table", {"path": str(output), "count": len(mapping)})
        return output, len(mapping)

    def merge_live_translation(self, source: str, target: str, kind: str = "realtime_translated") -> None:
        source = str(source or "").strip()
        target = str(target or "").strip()
        if not source or not target:
            return
        sanitized = self._sanitize_renpy_text(source, target)
        with _LIVE_SERVER_LOCK:
            translations = _LIVE_SERVER_STATE.setdefault("translations", {})
            if isinstance(translations, dict):
                translations[source] = sanitized
                for candidate in _live_translation_candidates(source):
                    translations.setdefault(candidate, sanitized)
            event = {
                "time": time.time(),
                "kind": kind,
                "source": source,
                "displayed": source,
                "target": sanitized,
                "matched": True,
                "type": "",
                "interact": True,
            }
            _LIVE_SERVER_STATE.setdefault("events", []).append(event)
            seen = _LIVE_SERVER_STATE.setdefault("seen", {})
            if isinstance(seen, dict):
                seen[f"{kind}\0{source}"] = sanitized
            events = _LIVE_SERVER_STATE.get("events", [])
            if isinstance(events, list) and len(events) > 2000:
                del events[: len(events) - 2000]
        _append_live_log("tool", "merge_live_translation", {"source": source[:180], "target": sanitized[:180], "kind": kind})
        self.notify_game_refresh()

    def notify_game_refresh(self) -> int:
        with _LIVE_SERVER_LOCK:
            seq = int(_LIVE_SERVER_STATE.get("notify_seq", 0)) + 1
            _LIVE_SERVER_STATE["notify_seq"] = seq
        _append_live_log("tool", "notify_game_refresh", {"seq": seq})
        return seq

    def force_live_text(self, text: str) -> int:
        value = str(text or "").strip()
        if not value:
            return 0
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE["force_text"] = value
            _LIVE_SERVER_STATE["force_seq"] = int(_LIVE_SERVER_STATE.get("force_seq", 0)) + 1
        _append_live_log("tool", "force_live_text", {"text": value[:180], "force_seq": int(_LIVE_SERVER_STATE.get("force_seq", 0))})
        return self.notify_game_refresh()

    def append_live_debug_event(self, kind: str, source: str, displayed: str = "", target: str = "", matched: bool = False) -> None:
        source = str(source or "").strip()
        displayed = str(displayed or source)
        target = str(target or "")
        if not source and not displayed and not target:
            return
        with _LIVE_SERVER_LOCK:
            event = {
                "time": time.time(),
                "kind": str(kind or "realtime_status"),
                "source": source,
                "displayed": displayed,
                "target": target,
                "matched": bool(matched),
                "type": "",
                "interact": True,
            }
            _LIVE_SERVER_STATE.setdefault("events", []).append(event)
            events = _LIVE_SERVER_STATE.get("events", [])
            if isinstance(events, list) and len(events) > 2000:
                del events[: len(events) - 2000]

    def read_live_debug_entries(self, limit: int = 200) -> list[dict[str, object]]:
        with _LIVE_SERVER_LOCK:
            events = list(_LIVE_SERVER_STATE.get("events", []))[-max(1, limit):]
        if events:
            return [event for event in events if isinstance(event, dict)]
        path = self.live_seen_path()
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        entries: list[dict[str, object]] = []
        for line in lines[-max(1, limit):]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
        return entries

    def live_bridge_status(self) -> dict[str, object]:
        with _LIVE_SERVER_LOCK:
            events = _LIVE_SERVER_STATE.get("events", [])
            translations = _LIVE_SERVER_STATE.get("translations", {})
            seen = _LIVE_SERVER_STATE.get("seen", {})
            last_event = events[-1] if isinstance(events, list) and events else {}
            return {
                "event_count": len(events) if isinstance(events, list) else 0,
                "translation_count": len(translations) if isinstance(translations, dict) else 0,
                "seen_count": len(seen) if isinstance(seen, dict) else 0,
                "last_event": dict(last_event) if isinstance(last_event, dict) else {},
            }

    def needs_runtime_extraction(self) -> bool:
        if self.runtime_export_path().exists():
            return False
        source_files = [
            path
            for path in self.scripts_dir.rglob("*.rpy")
            if not self._is_translation_file(path) and not self._is_generated_file(path)
        ]
        compiled_or_archived = any(self.scripts_dir.rglob("*.rpyc")) or any(self.scripts_dir.rglob("*.rpa"))
        return compiled_or_archived and not source_files

    def can_runtime_extract(self) -> bool:
        return any(self.scripts_dir.rglob("*.rpyc")) or any(self.scripts_dir.rglob("*.rpa"))

    def prepare_source_tree(self) -> dict[str, int | str]:
        rpy_count = len(list(self.scripts_dir.rglob("*.rpy")))
        rpyc_files = list(self.scripts_dir.rglob("*.rpyc"))
        rpa_files = list(self.scripts_dir.rglob("*.rpa"))
        decompiled = 0
        extracted = 0
        if rpa_files:
            extracted += self._run_unrpa(rpa_files)
        if rpyc_files:
            decompiled += self._run_unrpyc(rpyc_files)
        return {
            "rpy": len(list(self.scripts_dir.rglob("*.rpy"))),
            "rpyc": len(list(self.scripts_dir.rglob("*.rpyc"))),
            "rpa": len(list(self.scripts_dir.rglob("*.rpa"))),
            "decompiled": decompiled,
            "extracted": extracted,
        }

    def _run_unrpa(self, archives: list[Path]) -> int:
        try:
            import unrpa  # type: ignore
        except Exception:
            return 0
        extracted = 0
        for archive in archives:
            try:
                out_dir = archive.parent
                result = getattr(unrpa, "extract", None)
                if callable(result):
                    result(str(archive), str(out_dir))
                else:
                    extractor = getattr(unrpa, "UnRPA", None)
                    if callable(extractor):
                        instance = extractor(str(archive))
                        if hasattr(instance, "extract"):
                            instance.extract(str(out_dir))
                        elif hasattr(instance, "unpack"):
                            instance.unpack(str(out_dir))
                        else:
                            continue
                    else:
                        continue
                extracted += 1
            except Exception:
                continue
        return extracted

    def _run_unrpyc(self, compiled_files: list[Path]) -> int:
        try:
            import unrpyc  # type: ignore
        except Exception:
            return 0
        decompiled = 0
        for compiled in compiled_files:
            try:
                runner = getattr(unrpyc, "decompile_rpyc", None)
                if callable(runner):
                    runner(str(compiled), None, overwrite=True)
                    decompiled += 1
            except Exception:
                continue
        return decompiled

    def apply_translations(self, translations: dict[str, TranslationEntry]) -> int:
        entries = self._safe_translation_entries(translations.values())
        self._backup_scripts()
        self._backup_translations()
        self.restore_original_scripts()
        count = self._write_translation_strings_file(entries)
        if count:
            self._write_language_bootstrap()
            self._write_embedded_text_patch(entries)
            issues = self.validate_embedded_scripts()
            if issues and not self._repair_generated_translation_files(entries, issues):
                self.restore_backup()
                raise RuntimeError("Ren'Py 生成翻译脚本校验失败，已自动回滚：" + "；".join(issues[:5]))
        return count

    def build_runtime_translation_patch(self, translations: dict[str, TranslationEntry]) -> tuple[Path, int]:
        entries = self._safe_translation_entries(translations.values())
        mapping = {
            entry.source: self._sanitize_renpy_text(entry.source, entry.target)
            for entry in entries
        }
        output = self.scripts_dir / RUNTIME_PATCH_NAME
        rendered_mapping = json.dumps(mapping, ensure_ascii=False, indent=4)
        rendered_mapping = rendered_mapping.replace("\n", "\n    ")
        lines = [
            "# Auto-generated temporary runtime translation patch.",
            "# Delete this file to disable temporary text replacement.",
            "init -999 python:",
            f"    _rpgrtl_runtime_translations = {rendered_mapping}",
            "    _rpgrtl_previous_replace_text = config.replace_text",
            "",
            "    def _rpgrtl_replace_text(s):",
            "        if not isinstance(s, str):",
            "            return s",
            "        original = s",
            "        if _rpgrtl_previous_replace_text is not None:",
            "            s = _rpgrtl_previous_replace_text(s)",
            "        return _rpgrtl_runtime_translations.get(",
            "            s,",
            "            _rpgrtl_runtime_translations.get(original, _rpgrtl_runtime_translations.get(s.strip(), s))",
            "        )",
            "",
            "    config.replace_text = _rpgrtl_replace_text",
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return output, len(mapping)

    def _write_embedded_text_patch(self, entries: list[TranslationEntry]) -> int:
        entries = self._safe_translation_entries(entries)
        mapping = {
            entry.source: self._sanitize_renpy_text(entry.source, entry.target)
            for entry in entries
        }
        if not mapping:
            return 0
        output = self.scripts_dir / EMBEDDED_PATCH_NAME
        rendered_mapping = json.dumps({k: v.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") for k, v in mapping.items()}, ensure_ascii=False, indent=4)
        rendered_mapping = rendered_mapping.replace("\n", "\n    ")
        lines = [
            "# Auto-generated permanent text replacement patch.",
            "# Delete this file to restore original display text for compiled-only Ren'Py scripts.",
            "init -999 python:",
            f"    _rpgrtl_embedded_translations = {rendered_mapping}",
            "    _rpgrtl_previous_replace_text = config.replace_text",
            "",
            "    def _rpgrtl_embedded_replace_text(s):",
            "        if not isinstance(s, str):",
            "            return s",
            "        original = s",
            "        if _rpgrtl_previous_replace_text is not None:",
            "            s = _rpgrtl_previous_replace_text(s)",
            "        return _rpgrtl_embedded_translations.get(",
            "            s,",
            "            _rpgrtl_embedded_translations.get(original, _rpgrtl_embedded_translations.get(s.strip(), s))",
            "        )",
            "",
            "    config.replace_text = _rpgrtl_embedded_replace_text",
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return len(mapping)

    def _write_translation_strings_file(self, entries: list[TranslationEntry]) -> int:
        entries = self._safe_translation_entries(entries)
        self._backup_translations()
        tl_dir = self.scripts_dir / "tl" / "schinese"
        tl_dir.mkdir(parents=True, exist_ok=True)
        output = tl_dir / "codex_generated.rpy"
        existing_sources = self._existing_language_old_strings(tl_dir, output)
        written_sources: set[str] = set()

        # 流式写入 — 避免构建超大 lines 列表和 "\n".join() 内存尖峰
        with output.open("w", encoding="utf-8", newline="\n") as f:
            f.write("# Auto-generated by RPGRenPyLocalizer\n")
            count = 0
            for entry in sorted(entries, key=lambda item: item.entry_id):
                if entry.source in existing_sources or entry.source in written_sources:
                    continue
                if not entry.target.strip():
                    continue
                if count == 0:
                    # Only write the header when we have actual entries
                    f.write("translate schinese strings:\n")
                    f.write("\n")
                if count % 200 == 0:
                    time.sleep(0)
                escaped_source = self._escape(entry.source)
                escaped_target = self._escape(self._sanitize_renpy_text(entry.source, entry.target))
                f.write(f"    # {entry.file} | {entry.context}\n")
                f.write(f'    old "{escaped_source}"\n')
                f.write(f'    new "{escaped_target}"\n')
                f.write("\n")
                written_sources.add(entry.source)
                count += 1

        # If no entries were written, remove the empty file
        if count == 0:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass

        return count

    def _existing_language_old_strings(self, tl_dir: Path, generated_output: Path) -> set[str]:
        existing: set[str] = set()
        try:
            generated_resolved = generated_output.resolve()
        except OSError:
            generated_resolved = generated_output
        for file_path in sorted(tl_dir.rglob("*.rpy")):
            try:
                if file_path.resolve() == generated_resolved:
                    continue
            except OSError:
                continue
            if file_path.name == "codex_generated.rpy":
                continue
            try:
                lines = self._read_text_file(file_path).splitlines()
            except OSError:
                continue
            for line in lines:
                match = STRING_PATTERN.match(line)
                if match:
                    existing.add(self._unescape(match.group("old")))
        return existing

    def _replace_script_sources(self, entries: list[TranslationEntry]) -> set[str]:
        self._backup_scripts()
        grouped: dict[Path, list[TranslationEntry]] = {}
        for entry in entries:
            if not entry.file.lower().endswith(".rpy"):
                continue
            file_path = self._resolve_script_file(entry.file)
            if not file_path:
                continue
            grouped.setdefault(file_path, []).append(entry)

        changed_ids: set[str] = set()
        for file_index, (file_path, file_entries) in enumerate(grouped.items()):
            if file_index % 10 == 0:
                time.sleep(0)
            lines = self._read_text_file(file_path).splitlines()
            changed = False
            for index, entry in enumerate(file_entries):
                if index % 100 == 0:
                    time.sleep(0)
                try:
                    line_index = int(entry.entry_id.rsplit("::", 1)[-1])
                except ValueError:
                    continue
                if line_index < 0 or line_index >= len(lines):
                    continue
                original = lines[line_index]
                match = QUOTE_PATTERN.match(original)
                if not match:
                    continue
                current_text = self._unescape(match.group("text"))
                if current_text != entry.source:
                    continue
                prefix = original[: match.start("text")]
                suffix = original[match.end("text") :]
                lines[line_index] = f"{prefix}{self._escape(self._sanitize_renpy_text(entry.source, entry.target))}{suffix}"
                changed_ids.add(entry.entry_id)
                changed = True
            if changed:
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return changed_ids

    def restore_original_scripts(self) -> int:
        backup_root = self.project.root / ".rpgrtl_backup" / "game"
        if not backup_root.exists():
            return self.clear_generated_translation_files()
        removed = self.clear_generated_translation_files()
        restored = 0
        for source in backup_root.rglob("*"):
            if source.is_dir():
                continue
            rel = source.relative_to(backup_root)
            target = self.scripts_dir / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                restored += 1
            except OSError:
                continue
        return removed + restored + self.clear_generated_translation_files()

    def clear_generated_translation_files(self) -> int:
        removed = 0
        targets = list(sorted(self.scripts_dir.rglob("zz_rpgrtl_*.rpy")))
        targets.extend(
            [
                self.scripts_dir / LANGUAGE_BOOTSTRAP_NAME,
                self.scripts_dir / "tl" / "schinese" / "codex_generated.rpy",
            ]
        )
        for path in targets:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def _resolve_script_file(self, file_name: str) -> Path | None:
        candidate = self.project.root / file_name
        if candidate.exists():
            return candidate
        candidate = self.scripts_dir / file_name
        if candidate.exists():
            return candidate
        matches = list(self.scripts_dir.rglob(Path(file_name).name))
        if len(matches) == 1:
            return matches[0]
        return None

    def _write_language_bootstrap(self) -> None:
        output = self.scripts_dir / LANGUAGE_BOOTSTRAP_NAME
        lines = [
            "# Auto-generated by RPGRenPyLocalizer",
            "init -999 python:",
            '    config.language = "schinese"',
            "",
            "init -998 python:",
            "    import os as _rpgrtl_os",
            "    _rpgrtl_cjk_font = None",
            "    for _rpgrtl_font in (",
            '        r"C:/Windows/Fonts/msyh.ttc",',
            '        r"C:/Windows/Fonts/msyh.ttf",',
            '        r"C:/Windows/Fonts/simhei.ttf",',
            '        r"C:/Windows/Fonts/simsun.ttc",',
            '        r"C:/Windows/Fonts/NotoSansCJK-Regular.ttc",',
            "    ):",
            "        if _rpgrtl_os.path.exists(_rpgrtl_font):",
            "            _rpgrtl_cjk_font = _rpgrtl_font",
            "            break",
            "    if _rpgrtl_cjk_font:",
            "        try:",
            "            gui.text_font = _rpgrtl_cjk_font",
            "            gui.name_text_font = _rpgrtl_cjk_font",
            "            gui.interface_text_font = _rpgrtl_cjk_font",
            "        except Exception:",
            "            pass",
            "        for _rpgrtl_style_name in (\"default\", \"say_dialogue\", \"say_label\", \"choice_button_text\", \"button_text\", \"input\", \"textbutton_text\"):",
            "            try:",
            "                getattr(style, _rpgrtl_style_name).font = _rpgrtl_cjk_font",
            "            except Exception:",
            "                pass",
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def list_data_records(self) -> list[DataRecord]:
        records: list[DataRecord] = []
        for file_path in sorted(self._candidate_files()):
            if self._is_translation_file(file_path):
                continue
            if file_path.suffix.lower() != ".rpy":
                continue
            for index, line in enumerate(self._read_text_file(file_path).splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                match = QUOTE_PATTERN.match(line)
                if not match:
                    continue
                text = self._unescape(match.group("text"))
                if not text.strip():
                    continue
                speaker = match.group("speaker") or "narrator"
                records.append(
                    DataRecord(
                        record_id=f"{file_path.relative_to(self.project.root)}::{index}",
                        label=speaker,
                        value=text,
                        file=str(file_path.relative_to(self.project.root)),
                        category="Ren'Py 脚本对白",
                        location=f"line {index}",
                        line_number=index,
                    )
                )
        return records

    def _candidate_files(self) -> list[Path]:
        files: list[Path] = []
        for pattern in ("*.rpy", "*.rpyc"):
            files.extend(sorted(self.scripts_dir.rglob(pattern)))
        seen: dict[str, Path] = {}
        for file_path in files:
            if self._is_translation_file(file_path) or self._is_generated_file(file_path):
                continue
            seen.setdefault(str(file_path.resolve()), file_path)
        return list(seen.values())

    def update_record(self, record: DataRecord, new_value: str) -> None:
        self._backup_scripts()
        file_path = self.project.root / record.file
        lines = self._read_text_file(file_path).splitlines()
        if not record.line_number or record.line_number < 1 or record.line_number > len(lines):
            raise ValueError("无法定位要修改的 Ren'Py 行。")
        original = lines[record.line_number - 1]
        match = QUOTE_PATTERN.match(original)
        if not match:
            raise ValueError("目标行不是可直接编辑的对白/文本行。")
        prefix = original[: match.start("text")]
        suffix = original[match.end("text") :]
        lines[record.line_number - 1] = f"{prefix}{self._escape(new_value)}{suffix}"
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def _extract_from_translation_file(self, file_path: Path) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        lines = self._read_text_file(file_path).splitlines()
        current_old = ""
        for index, line in enumerate(lines):
            match_old = STRING_PATTERN.match(line)
            if match_old:
                current_old = self._unescape(match_old.group("old"))
                continue

            stripped = line.strip()
            if stripped.startswith("new ") and current_old:
                target = stripped[4:].strip()
                if target.startswith('"') and target.endswith('"'):
                    entries.append(
                        TranslationEntry(
                            entry_id=f"{file_path.name}::{index}",
                        source=current_old,
                        target=self._unescape(target[1:-1]),
                        file=file_path.name,
                        context="translation strings",
                        category="dialogue",
                    )
                )
                current_old = ""
        return entries

    def _extract_from_runtime_cache(self) -> list[TranslationEntry]:
        path = self.runtime_export_path()
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not payload.get("ok", False):
            return []
        entries: list[TranslationEntry] = []
        for index, item in enumerate(payload.get("entries", [])):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            if not source:
                continue
            file_name = str(item.get("file", "compiled"))
            context = str(item.get("context", ""))
            identifier = str(item.get("identifier", ""))
            line = item.get("line", 0)
            category = str(item.get("category", "dialogue") or "dialogue")
            entry_id = f"runtime::{file_name}::{identifier}::{line}::{index}"
            normalized_category = category if category in {"dialogue", "choice"} else "system"
            entries.append(
                TranslationEntry(
                    entry_id=entry_id,
                    source=source,
                    file=file_name or "compiled",
                    context=context,
                    category=normalized_category,
                )
            )
        return entries

    def _extract_from_script_file(self, file_path: Path) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        if file_path.suffix.lower() == ".rpyc":
            return self._extract_from_binary_file(file_path)
        for index, line in enumerate(self._read_text_file(file_path).splitlines()):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = QUOTE_PATTERN.match(line)
            if not match:
                continue
            text = self._unescape(match.group("text"))
            if not text.strip():
                continue
            speaker = match.group("speaker") or "narrator"
            suffix = line[match.end("text") :]
            is_choice = not match.group("speaker") and bool(MENU_CHOICE_SUFFIX_PATTERN.match(suffix))
            entries.append(
                TranslationEntry(
                    entry_id=f"{file_path.name}::{index}",
                    source=text,
                    file=file_path.name,
                    context="menu choice" if is_choice else speaker,
                    category="choice" if is_choice else "dialogue",
                )
            )
        return self._deduplicate(entries)

    def _extract_from_binary_file(self, file_path: Path) -> list[TranslationEntry]:
        entries: list[TranslationEntry] = []
        try:
            payload = file_path.read_bytes()
        except OSError:
            return entries
        seen: set[str] = set()
        for index, raw in enumerate(RPA_TEXT_PATTERN.findall(payload)):
            text = raw.decode("utf-8", errors="ignore").strip()
            text = text.replace("\\n", "\n").strip()
            if not self._looks_like_translatable_text(text) or text in seen:
                continue
            seen.add(text)
            entries.append(
                TranslationEntry(
                    entry_id=f"{file_path.name}::compiled::{index}",
                    source=text,
                    file=file_path.name,
                    context="compiled script",
                    category="dialogue",
                )
            )
        return entries

    @staticmethod
    def _is_translation_file(file_path: Path) -> bool:
        return "tl" in file_path.parts

    @staticmethod
    def _is_generated_file(file_path: Path) -> bool:
        return file_path.name in {RUNTIME_PATCH_NAME, EMBEDDED_PATCH_NAME, LANGUAGE_BOOTSTRAP_NAME, EXTRACTOR_NAME}

    @staticmethod
    def _read_text_file(file_path: Path) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp932", "gbk"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return file_path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _looks_like_translatable_text(text: str) -> bool:
        if len(text) < 2 or len(text) > 240:
            return False
        if text.startswith(("$", "#", "renpy.", "config.", "gui.")):
            return False
        if IDENTIFIER_PATTERN.match(text):
            return False
        return any("\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff" or "a" <= char.lower() <= "z" for char in text)

    @staticmethod
    def _sanitize_renpy_text(source: str, text: str) -> str:
        source_tokens = [token for token in re.findall(r'\[[^\]]+\]|\{[^}]+\}', source)]
        sanitized = RenPyService._clean_translation_target(text)
        sanitized = MARKDOWN_LINK_PATTERN.sub(lambda match: f"{match.group(1)} (LINK)", sanitized)
        sanitized = re.sub(r"https?://\S+", "LINK", sanitized)

        protected: list[tuple[str, str]] = []
        for index, token in enumerate(source_tokens):
            placeholder = f"__RPGRTL_TOKEN_{index}__"
            if token in sanitized:
                sanitized = sanitized.replace(token, placeholder)
                protected.append((placeholder, token))

        sanitized = sanitized.translate(str.maketrans({"[": "［", "]": "］", "{": "｛", "}": "｝"}))

        for placeholder, token in protected:
            sanitized = sanitized.replace(placeholder, token)
        return sanitized

    @staticmethod
    def _clean_translation_target(text: str) -> str:
        normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
        normalized = PASTED_PLACEHOLDER_PATTERN.sub("", normalized)
        lines = [line for line in normalized.split("\n") if line.strip()]
        return "\n".join(lines).strip()

    @staticmethod
    def _safe_translation_entries(entries) -> list[TranslationEntry]:
        safe_entries: list[TranslationEntry] = []
        for entry in entries:
            if not entry.source.strip():
                continue
            target = RenPyService._clean_translation_target(entry.target)
            if not target:
                continue
            safe_entries.append(
                TranslationEntry(
                    entry_id=entry.entry_id,
                    source=entry.source,
                    target=target,
                    file=entry.file,
                    context=entry.context,
                    category=entry.category,
                )
            )
        return safe_entries

    def validate_embedded_scripts(self) -> list[str]:
        issues: list[str] = []
        paths = list(sorted(self.scripts_dir.rglob("zz_rpgrtl_*.rpy")))
        generated_strings = self.scripts_dir / "tl" / "schinese" / "codex_generated.rpy"
        if generated_strings.exists():
            paths.append(generated_strings)
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(f"{path.name}: {exc}")
                continue
            if text.count('"""') % 2 != 0 or text.count("'''") % 2 != 0:
                issues.append(f"{path.name}: 三引号数量异常")
            if path.name == "codex_generated.rpy":
                if not self._translation_file_pairs_are_valid(path):
                    issues.append(f"{path.name}: old/new 翻译对格式异常")
            elif path.name == EMBEDDED_PATCH_NAME:
                if not self._embedded_patch_looks_valid(text):
                    issues.append(f"{path.name}: 嵌入补丁结构异常")
            elif path.name == RUNTIME_PATCH_NAME:
                if not self._runtime_patch_looks_valid(text):
                    issues.append(f"{path.name}: 运行时补丁结构异常")
            elif path.name == LIVE_BRIDGE_NAME:
                if not self._live_bridge_looks_valid(text):
                    issues.append(f"{path.name}: 实时桥接结构异常")
        return issues

    @staticmethod
    def _embedded_patch_looks_valid(text: str) -> bool:
        return (
            "_rpgrtl_embedded_translations = {" in text
            and "def _rpgrtl_embedded_replace_text" in text
            and "config.replace_text = _rpgrtl_embedded_replace_text" in text
        )

    @staticmethod
    def _runtime_patch_looks_valid(text: str) -> bool:
        return (
            "_rpgrtl_runtime_translations = {" in text
            and "def _rpgrtl_replace_text" in text
            and "config.replace_text = _rpgrtl_replace_text" in text
        )

    @staticmethod
    def _live_bridge_looks_valid(text: str) -> bool:
        return (
            "def _rpgrtl_hook_do_display" in text
            and "def _rpgrtl_hook_prefix_suffix" in text
            and "def _rpgrtl_hook_set_text" in text
            and "def _rpgrtl_hook_character_call" in text
            and "def _rpgrtl_lookup" in text
            and "/pull" in text
            and "import renpy" not in text
        )

    def _translation_file_pairs_are_valid(self, path: Path) -> bool:
        current_old = ""
        found = 0
        for line in self._read_text_file(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped == "translate schinese strings:":
                continue
            match_old = STRING_PATTERN.match(line)
            if match_old:
                current_old = match_old.group("old")
                continue
            if stripped.startswith("new "):
                if not current_old:
                    return False
                target = stripped[4:].strip()
                if not (target.startswith('"') and target.endswith('"')):
                    return False
                current_old = ""
                found += 1
                continue
            return False
        return found > 0 and not current_old

    def _repair_generated_translation_files(self, entries: list[TranslationEntry], issues: list[str]) -> bool:
        try:
            repaired = self._safe_translation_entries(entries)
            if not repaired:
                return False
            self._write_translation_strings_file(repaired)
            self._write_language_bootstrap()
            self._write_embedded_text_patch(repaired)
            return not self.validate_embedded_scripts()
        except Exception:
            return False

    def repair_translation_entry_with_llm(self, entry: TranslationEntry, provider: str, api_key: str, model: str, base_url: str = "") -> str | None:
        from urllib import request, error

        prompt = json.dumps(
            {
                "task": "repair_renpy_translation",
                "source": entry.source,
                "target": entry.target,
                "rules": [
                    "只返回修复后的中文译文，不要解释",
                    "保留所有 Ren'Py 控制符、变量占位符、tag、换行和标点结构",
                    "不要新增多余的大括号或方括号",
                    "如果原译文明显不安全，尽量改成更稳妥的短句",
                ],
            },
            ensure_ascii=False,
        )
        system_prompt = (
            "你是 Ren'Py 翻译修复器。目标是修复一条可能导致脚本校验失败的译文。"
            "只输出修复后的译文，不要 JSON，不要解释。"
        )
        try:
            if provider == "OpenAI":
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "stream": False,
                }
                endpoint = self._chat_completions_url(base_url.strip() or "https://api.openai.com/v1")
                req = request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=120) as response:
                    raw = response.read().decode("utf-8")
                payload = json.loads(raw)
                text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = self._load_llm_json(text, "OpenAI")
                value = str(parsed.get("repair", "") or parsed.get("0", "") or "").strip()
                return value or None
            return None
        except (error.HTTPError, error.URLError, RuntimeError, json.JSONDecodeError):
            return None

    def restore_backup(self) -> int:
        backup_root = self.project.root / ".rpgrtl_backup"
        if not backup_root.exists():
            return 0
        self.restore_original_scripts()
        restored = 0
        for source_root, target_root in ((backup_root / "game", self.scripts_dir), (backup_root / "tl", self.scripts_dir / "tl")):
            if not source_root.exists():
                continue
            for source in source_root.rglob("*"):
                if source.is_dir():
                    continue
                rel = source.relative_to(source_root)
                target = target_root / rel
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    restored += 1
                except OSError:
                    continue
        return restored

    def _restore_backup_tree(self, source_root: Path, target_root: Path) -> int:
        restored = 0
        for source in source_root.rglob("*"):
            if source.is_dir():
                continue
            rel = source.relative_to(source_root)
            target = target_root / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                restored += 1
            except OSError:
                continue
        return restored

    def _backup_translations(self) -> None:
        source = self.scripts_dir / "tl"
        if not source.exists():
            return
        backup_root = self.project.root / ".rpgrtl_backup" / "tl"
        if backup_root.exists():
            return
        shutil.copytree(source, backup_root)

    def _backup_scripts(self) -> None:
        backup_root = self.project.root / ".rpgrtl_backup" / "game"
        if backup_root.exists():
            return
        shutil.copytree(self.scripts_dir, backup_root, ignore=shutil.ignore_patterns("tl", "zz_rpgrtl_*.rpy", LANGUAGE_BOOTSTRAP_NAME))

    @staticmethod
    def _escape(value: str) -> str:
        """转义 Ren'Py 字符串文本中的特殊字符。
        顺序必须为：反斜杠 → 控制符(换行/回车/制表符) → 双引号。
        顺序错误会导致二次转义。"""
        value = value.replace("\\", "\\\\")
        value = value.replace("\n", "\\n")
        value = value.replace("\r", "\\r")
        value = value.replace("\t", "\\t")
        value = value.replace('"', '\\"')
        return value

    @staticmethod
    def _unescape(value: str) -> str:
        """反转义 Ren'Py 字符串文本。
        顺序必须为：\\\" → \"  然后 \\\\ → \\。
        顺序错误会导致反斜杠被二次处理。"""
        value = value.replace('\\"', '"')
        value = value.replace("\\n", "\n")
        value = value.replace("\\r", "\r")
        value = value.replace("\\t", "\t")
        value = value.replace("\\\\", "\\")
        return value

    @staticmethod
    def _deduplicate(entries: list[TranslationEntry]) -> list[TranslationEntry]:
        by_source: dict[str, TranslationEntry] = {}
        for entry in entries:
            by_source.setdefault(entry.source, entry)
        return list(by_source.values())
