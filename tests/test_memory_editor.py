from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from toolkit.api.server import ApiError, ToolkitApi
from toolkit.memory_editor import LocalMemoryScanner, MemoryScanSession
from toolkit.models import ProjectInfo


class _FakeScanner:
    def list_project_processes(self, root, launcher, known_pids):
        return [{"pid": 4321, "name": "Demo.exe", "path": str(root / "Demo.exe"), "launchedByTool": True}]

    def start_scan(self, session_id, pid, process_name, value, value_type):
        return MemoryScanSession(session_id, pid, process_name, value_type, [0x1000, 0x2000], False, 1, last_value=int(value))

    def refine_scan(self, session, value):
        session.addresses = [0x2000]
        session.pass_count += 1
        session.last_value = int(value)
        return session

    def write_value(self, session, address, value):
        if address not in session.addresses:
            from toolkit.memory_editor import MemoryScanError
            raise MemoryScanError("address is not part of the active result set")
        return int(value)


class MemoryEditorTests(unittest.TestCase):
    def test_number_codecs_and_session_preview(self):
        scanner = LocalMemoryScanner()
        self.assertEqual(scanner._unpack_value(scanner._pack_value(-42, "int32"), "int32"), -42)
        self.assertEqual(scanner._unpack_value(scanner._pack_value(42, "uint32"), "uint32"), 42)
        session = MemoryScanSession("session", 7, "Demo.exe", "int32", [0x10, 0x20], pass_count=1, last_value=42)
        payload = session.payload()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["results"][0]["address"], "0x0000000000000010")

    def test_api_enforces_current_scan_result_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            launcher = root / "Demo.exe"
            launcher.write_bytes(b"MZ")
            api = ToolkitApi(root, config_dir=root / "config")
            api.project = ProjectInfo("Generic Windows Game", root, root, launcher_path=launcher)
            api.memory_scanner = _FakeScanner()

            started = api.memory_scan_start({"pid": 4321, "value": "125", "valueType": "int32"})
            self.assertEqual(started["count"], 2)
            refined = api.memory_scan_refine({"sessionId": started["sessionId"], "value": "130"})
            self.assertEqual(refined["count"], 1)
            self.assertEqual(refined["pass"], 2)
            written = api.memory_write({"sessionId": started["sessionId"], "address": "0x2000", "value": "999999"})
            self.assertEqual(written["value"], 999999)
            with self.assertRaises(ApiError):
                api.memory_write({"sessionId": started["sessionId"], "address": "0x1000", "value": "1"})


if __name__ == "__main__":
    unittest.main()
