from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from toolkit.models import ProjectInfo
from toolkit.api.server import ToolkitApi
from toolkit.renpy import RenPyService, _LIVE_SERVER_LOCK, _LIVE_SERVER_STATE


class RenPyLiveBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        game_dir = self.root / "game"
        game_dir.mkdir()
        self.service = RenPyService(
            ProjectInfo(engine="Ren'Py", root=self.root, game_dir=game_dir, scripts_dir=game_dir)
        )
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE.clear()
            _LIVE_SERVER_STATE.update(
                {"translations": {}, "events": [], "seen": {}, "notify_seq": 0, "force_text": "", "pre_translate_queue": []}
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_batch_merge_persists_and_notifies_once(self) -> None:
        seq = self.service.merge_live_translations(
            {"Hello": "你好", "Score [score]": "得分 [score]"}, kind="automatic"
        )

        payload = json.loads(self.service.live_translation_path().read_text(encoding="utf-8"))
        self.assertEqual(seq, 1)
        self.assertEqual(payload["translations"]["Hello"], "你好")
        self.assertEqual(payload["translations"]["Score [score]"], "得分 [score]")
        self.assertFalse(self.service.live_translation_path().with_suffix(".json.tmp").exists())

    def test_control_tokens_must_be_preserved_in_order(self) -> None:
        self.assertTrue(RenPyService.control_tokens_preserved("Hello [player] {b}world{/b}", "你好 [player] {b}世界{/b}"))
        self.assertFalse(RenPyService.control_tokens_preserved("Hello [player]", "你好"))
        self.assertFalse(RenPyService.control_tokens_preserved("{b}A{/b}", "{/b}甲{b}"))

    def test_runtime_extraction_excludes_system_strings(self) -> None:
        self.service.runtime_export_path().parent.mkdir(parents=True, exist_ok=True)
        self.service.runtime_export_path().write_text(
            json.dumps({"ok": True, "entries": [
                {"source": "A line", "category": "dialogue", "file": "script.rpy"},
                {"source": "A system label", "category": "system", "file": "gui.rpy"},
            ]}, ensure_ascii=False),
            encoding="utf-8",
        )
        entries = self.service.extract_translations()
        self.assertEqual([entry.source for entry in entries], ["A line"])

    def test_malformed_font_tags_are_removed_before_cache_write(self) -> None:
        target = "｛font = C:/Windows/Fonts/msyh.ttc｝行了行了 ……好吧。 {/font}"
        sanitized = RenPyService._sanitize_renpy_text("Yeah, yeah... Okay.", target)
        self.assertNotIn("font", sanitized.lower())
        self.assertNotIn("{/font}", sanitized)
        self.assertEqual(sanitized, "行了行了 ……好吧。")

    def test_http_hook_capture_translate_refresh_round_trip(self) -> None:
        def post(endpoint: str, payload: dict) -> dict:
            request = urllib.request.Request(
                "http://127.0.0.1:32180" + endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))

        self.service.start_live_bridge_server(clear_events=True)
        try:
            captured = post("/pre_translate", {"texts": ["Hello [player]"]})
            self.assertEqual(captured["queued"], ["Hello [player]"])
            self.assertEqual(self.service.take_live_translation_candidates(), ["Hello [player]"])
            self.service.merge_live_translations({"Hello [player]": "你好 [player]"}, kind="automatic")
            replaced = post("/translation_batch", {"texts": ["Hello [player]"]})
            self.assertEqual(replaced["translations"]["Hello [player]"], "你好 [player]")
            missing = post("/translation_batch", {"texts": ["Later"]})
            self.assertEqual(missing["translations"], {})
            self.assertEqual(self.service.take_live_translation_candidates(), ["Later"])
            post("/notify", {"pid": 12345})
            self.assertTrue(self.service.live_bridge_status()["connected"])
        finally:
            self.service.stop_live_bridge_server()

    def test_activating_project_replaces_cross_project_state(self) -> None:
        self.service.live_translation_path().parent.mkdir(parents=True)
        self.service.live_translation_path().write_text(
            json.dumps({"version": 1, "translations": {"New": "新"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        with _LIVE_SERVER_LOCK:
            _LIVE_SERVER_STATE["project_root"] = "C:/other-game"
            _LIVE_SERVER_STATE["translations"] = {"Old": "旧"}
            _LIVE_SERVER_STATE["events"] = [{"kind": "old"}]
            _LIVE_SERVER_STATE["pre_translate_queue"] = ["Old queue"]

        self.service._activate_live_project(clear_events=True)

        with _LIVE_SERVER_LOCK:
            self.assertEqual(_LIVE_SERVER_STATE["project_root"], str(self.root.resolve()))
            self.assertEqual(_LIVE_SERVER_STATE["translations"], {"New": "新"})
            self.assertEqual(_LIVE_SERVER_STATE["events"], [])
            self.assertEqual(_LIVE_SERVER_STATE["pre_translate_queue"], [])

    def test_api_worker_translates_and_merges_a_batch(self) -> None:
        stop_event = __import__("threading").Event()

        class FakeService:
            def __init__(self) -> None:
                self.returned = False
                self.merged = {}

            def take_live_translation_candidates(self, _limit: int) -> list[str]:
                if self.returned:
                    return []
                self.returned = True
                return ["Hello", "Start"]

            def requeue_live_translation_candidates(self, _values: list[str]) -> None:
                self.fail("unexpected requeue")

            def merge_live_translations(self, values: dict[str, str], kind: str) -> int:
                self.merged = {"values": values, "kind": kind}
                stop_event.set()
                return 1

        api = ToolkitApi(self.root, config_dir=self.root / "config")
        api.live_worker_project = "project"
        api.live_worker_stats.update({"running": True, "translated": 0, "failures": 0})
        api._live_ai_config = lambda: {"provider": "openai-compatible", "apiKey": "key", "baseUrl": "https://example.test/v1", "model": "model", "targetLang": "简体中文", "batchSize": 20}
        api._translate_openai_compatible = lambda sources, _config: ["你好", "开始"]
        service = FakeService()

        api._live_worker_loop(service, stop_event, "project")

        self.assertEqual(service.merged["values"], {"Hello": "你好", "Start": "开始"})
        self.assertEqual(service.merged["kind"], "automatic")
        self.assertEqual(api.live_worker_stats["translated"], 2)


if __name__ == "__main__":
    unittest.main()
