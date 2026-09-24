from __future__ import annotations

import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

from toolkit.models import ProjectInfo, TranslationEntry
from toolkit.unity_xua import (
    UnityXuaService,
    decode_xua_segment,
    encode_xua_text,
    format_xua_line,
    parse_xua_line,
    read_xua_translation_file,
    write_xua_translation_file,
)


class XuaFormatTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self) -> None:
        raw = 'Hello = World\nnext "line"\\end'
        encoded = encode_xua_text(raw)
        self.assertNotIn("\n", encoded)
        self.assertIn("\\n", encoded)
        self.assertIn("\\=", encoded)
        self.assertEqual(decode_xua_segment(encoded), raw)

    def test_parse_line_and_comments(self) -> None:
        self.assertIsNone(parse_xua_line("// comment"))
        self.assertIsNone(parse_xua_line(""))
        pair = parse_xua_line(format_xua_line("こんにちは", "你好"))
        self.assertEqual(pair, ("こんにちは", "你好"))

    def test_write_and_read_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.txt"
            write_xua_translation_file(path, [("Hello.", "你好。"), ("a=b", "甲=乙")])
            pairs = read_xua_translation_file(path)
            self.assertIn(("Hello.", "你好。"), pairs)
            self.assertIn(("a=b", "甲=乙"), pairs)


class UnityXuaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "UnityPlayer.dll").write_bytes(b"x")
        self.service = UnityXuaService(ProjectInfo(engine="Unity", root=self.root, game_dir=self.root))

    def tearDown(self) -> None:
        from toolkit import unity_xua
        unity_xua.stop_live_bridge_server()
        self.temp_dir.cleanup()

    def test_install_writes_config_and_manual(self) -> None:
        notes = self.service.install_runtime_bridge()
        self.assertTrue(notes.is_file())
        self.assertTrue(self.service.config_path.is_file())
        config = self.service.config_path.read_text(encoding="utf-8")
        self.assertIn("Endpoint=CustomTranslate", config)
        self.assertIn("http://127.0.0.1:32182/xua/translate", config)
        self.assertTrue(self.service.manual_path.is_file())
        self.assertTrue(self.service.auto_path.is_file())

    def test_live_miss_returns_immediately_and_queues_for_worker(self) -> None:
        from toolkit import unity_xua

        unity_xua.start_live_bridge_server(self.service, clear_seen=True)
        try:
            url = "http://127.0.0.1:32182/xua/translate?" + urllib.parse.urlencode({"text": "Untranslated line"})
            with urllib.request.urlopen(url, timeout=2) as response:
                self.assertEqual(response.read().decode("utf-8"), "Untranslated line")
            status = unity_xua.live_status()
            self.assertEqual(status["xua_miss"], 1)
            self.assertEqual(status["queue_count"], 1)
        finally:
            unity_xua.stop_live_bridge_server()

    def test_export_import_roundtrip(self) -> None:
        entries = {
            "e1": TranslationEntry(entry_id="e1", source="Potion", target="药水", category="unity_xua"),
            "e2": TranslationEntry(entry_id="e2", source="Hello.", target="你好。", category="unity_xua"),
        }
        path = self.service.export_translations(entries)
        pairs = read_xua_translation_file(path)
        self.assertEqual(len(pairs), 2)
        imported = self.service.import_runtime_captures()
        sources = {item.source for item in imported}
        self.assertIn("Potion", sources)
        self.assertIn("Hello.", sources)
        self.assertEqual(self.service.lookup("Hello."), "你好。")


if __name__ == "__main__":
    unittest.main()
