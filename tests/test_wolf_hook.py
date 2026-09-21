from __future__ import annotations

import io
import json
import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path

from toolkit.wolf_hook import WolfHookBridge, WS_MAGIC_GUID
from toolkit.memory_editor import SmartGoldModifier, MemoryScanSession
from toolkit.models import ProjectInfo
from toolkit.unknown_game import (
    list_unknown_save_slots,
    list_unknown_save_snapshots,
    create_unknown_save_snapshot,
    restore_unknown_save_snapshot,
)


class _MockScanner:
    def __init__(self, initial_addresses: list[int]):
        self.initial_addresses = initial_addresses
        self.written: list[tuple[int, int]] = []

    def start_scan(self, session_id, pid, process_name, value, value_type):
        return MemoryScanSession(
            session_id=session_id,
            pid=pid,
            process_name=process_name,
            value_type=value_type,
            addresses=list(self.initial_addresses),
            pass_count=1,
            last_value=int(value),
        )

    def refine_scan(self, session, value):
        # Keep only odd addresses or subset
        session.addresses = [addr for addr in session.addresses if addr % 2 == 1]
        session.pass_count += 1
        session.last_value = int(value)
        return session

    def write_value(self, session, address, value):
        self.written.append((address, int(value)))
        return int(value)


class WolfHookTests(unittest.TestCase):
    def test_bridge_lifecycle_and_handshake(self) -> None:
        # Use an ephemeral port for testing
        bridge = WolfHookBridge(host="127.0.0.1", port=0)
        # Bind manually to get an allocated ephemeral port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        
        bridge.port = port
        bridge.start()
        try:
            time.sleep(0.1)
            # Connect a mock client
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("127.0.0.1", port))
            
            # Send HTTP Upgrade request
            key = "dGhlIHNhbXBsZSBub25jZQ=="
            req = (
                f"GET / HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n\r\n"
            )
            client.sendall(req.encode("latin1"))
            
            # Read handshake response
            resp = client.recv(1024).decode("latin1")
            self.assertIn("101 Switching Protocols", resp)
            self.assertIn("Sec-WebSocket-Accept:", resp)
            
            # Verify bridge is connected
            time.sleep(0.1)
            self.assertTrue(bridge.is_connected())
            
            # Client receives initial sync whoareyou command
            raw = client.recv(1024)
            self.assertGreater(len(raw), 2)
            # Unmask/parse server message (server sends unmasked frames)
            payload_len = raw[1] & 0x7F
            payload = raw[2:2 + payload_len].decode("utf-8")
            data = json.loads(payload)
            self.assertEqual(data.get("cmd"), "whoareyou")
            
            # Client replies with masked frame
            reply_text = json.dumps({"id": data["id"], "ret": "WOLF_MOCK"})
            reply_bytes = reply_text.encode("utf-8")
            mask = b"\x12\x34\x56\x78"
            masked_payload = bytearray(len(reply_bytes))
            for i in range(len(reply_bytes)):
                masked_payload[i] = reply_bytes[i] ^ mask[i % 4]
            frame = bytearray([0x81, 0x80 | len(reply_bytes)]) + mask + masked_payload
            client.sendall(frame)
            
            time.sleep(0.1)
            self.assertEqual(bridge.engine_name, "WOLF_MOCK")
            
            client.close()
        finally:
            bridge.stop()

    def test_wolf_hook_gold_and_variable_set(self) -> None:
        bridge = WolfHookBridge()
        bridge.cached_vars = [[1234, 5678, 90]]
        self.assertEqual(bridge.get_gold(), 1234)

        # Mock send_command to test set_gold
        sent_cmds = []
        def mock_send(cmd, args=None, timeout=3.0):
            sent_cmds.append((cmd, args))
            return {"ret": "OK"}

        bridge.send_command = mock_send
        res = bridge.set_gold(99999999)
        self.assertTrue(res)
        self.assertEqual(sent_cmds[0][0], "setVarVal")
        self.assertEqual(sent_cmds[0][1], [[[0, 0, 99999999], [0, 1, 99999999]]])

        # Test speed and noclip
        self.assertTrue(bridge.set_speed(3.5))
        self.assertEqual(bridge.cached_speed, 3.5)
        self.assertTrue(bridge.set_noclip(True))
        self.assertEqual(bridge.cached_noclip, True)
        self.assertTrue(bridge.set_noclip(False))
        self.assertEqual(bridge.cached_noclip, False)


class SmartGoldModifierTests(unittest.TestCase):
    def test_smart_gold_auto_applies_when_candidates_few(self) -> None:
        fake_scanner = _MockScanner(initial_addresses=[0x1000, 0x2000, 0x3000])
        modifier = SmartGoldModifier(scanner=fake_scanner)

        res = modifier.search_and_apply(pid=1234, current_gold=500, target_gold=99999999)
        self.assertTrue(res["ok"])
        self.assertTrue(res["applied"])
        self.assertEqual(res["count"], 3)
        self.assertEqual(len(fake_scanner.written), 3)
        self.assertEqual(fake_scanner.written[0][1], 99999999)

    def test_smart_gold_refines_when_candidates_many(self) -> None:
        # 10 candidates (> 8)
        addresses = [0x1000 + i for i in range(10)]
        fake_scanner = _MockScanner(initial_addresses=addresses)
        modifier = SmartGoldModifier(scanner=fake_scanner)

        res1 = modifier.search_and_apply(pid=1234, current_gold=100, target_gold=888888)
        self.assertTrue(res1["ok"])
        self.assertFalse(res1["applied"])
        self.assertEqual(res1["count"], 10)
        session_id = res1["sessionId"]

        # Refine with changed value
        res2 = modifier.refine_and_apply(session_id=session_id, new_gold=120, target_gold=888888)
        self.assertTrue(res2["ok"])
        self.assertTrue(res2["applied"])
        # Addresses ending in odd numbers remain: 5
        self.assertEqual(res2["count"], 5)
        self.assertEqual(len(fake_scanner.written), 5)
        self.assertEqual(fake_scanner.written[0][1], 888888)

    def test_smart_gold_no_matches_error(self) -> None:
        fake_scanner = _MockScanner(initial_addresses=[])
        modifier = SmartGoldModifier(scanner=fake_scanner)
        res = modifier.search_and_apply(pid=1234, current_gold=999)
        self.assertFalse(res["ok"])
        self.assertIn("未找到当前数值", res["error"])


class SaveSnapshotTests(unittest.TestCase):
    def test_list_and_snapshot_unknown_saves(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_dir = root / "Save"
            save_dir.mkdir()
            (save_dir / "SaveData01.sav").write_bytes(b"SAVE_SLOT_1_DATA")
            (save_dir / "SaveData02.sav").write_bytes(b"SAVE_SLOT_2_DATA")
            (save_dir / "System.sav").write_bytes(b"SYSTEM_DATA")

            project = ProjectInfo("Wolf RPG Editor", root, root)
            slots = list_unknown_save_slots(project)
            self.assertEqual(len(slots), 3)
            slot_names = [s["name"] for s in slots]
            self.assertIn("SaveData01.sav", slot_names)
            self.assertIn("SaveData02.sav", slot_names)
            self.assertIn("System.sav", slot_names)

            # Create snapshot
            snap_res = create_unknown_save_snapshot(project, label="测试备份")
            self.assertTrue(snap_res["ok"])
            snap_id = snap_res["snapshot"]["id"]

            snapshots = list_unknown_save_snapshots(project)
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]["label"], "测试备份")

            # Corrupt the save file
            (save_dir / "SaveData01.sav").write_bytes(b"CORRUPTED_GARBAGE")
            self.assertEqual((save_dir / "SaveData01.sav").read_bytes(), b"CORRUPTED_GARBAGE")

            # Restore snapshot
            rest_res = restore_unknown_save_snapshot(project, snap_id)
            self.assertTrue(rest_res["ok"])
            self.assertIn("SaveData01.sav", rest_res["restored"])
            self.assertEqual((save_dir / "SaveData01.sav").read_bytes(), b"SAVE_SLOT_1_DATA")


if __name__ == "__main__":
    unittest.main()
