from __future__ import annotations

"""Wolf RPG Editor live bridge and WebSocket server.

Implements a lightweight RFC 6455 WebSocket server compatible with MTool's
wolfHook.dll / wolfHook3.dll protocol on port 35421. Allows real-time reading and
writing of Wolf RPG variables, gold/money, game speed, and noclip status without
Cheat Engine.
"""

import base64
import hashlib
import json
import logging
import socket
import struct
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WOLF_PORT = 35421
WS_MAGIC_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WolfHookBridge:
    """Manages WebSocket communication with injected wolfHook.dll."""

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_WOLF_PORT) -> None:
        self.host = host
        self.port = port
        self.server_socket: socket.socket | None = None
        self.client_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.running = False
        self.lock = threading.Lock()
        
        # State caches
        self.connected = False
        self.engine_name = "WOLF"
        self.wolf_ver = "v2"
        self.cached_vars: list[list[int]] = []
        self.cached_speed: float = 1.0
        self.cached_noclip: bool = False
        self.last_sync_time: float = 0
        
        # Pending requests waiting for responses: req_id -> (Event, response_holder)
        self._pending_reqs: dict[str, tuple[threading.Event, list[dict[str, Any]]]] = {}
        self._req_counter = 0

    def start(self) -> None:
        """Start listening on 127.0.0.1:35421 in a background daemon thread."""
        with self.lock:
            if self.running:
                return
            self.running = True
            self.server_thread = threading.Thread(target=self._run_server, name="WolfHookServer", daemon=True)
            self.server_thread.start()

    def stop(self) -> None:
        """Stop the WebSocket server."""
        self.running = False
        with self.lock:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass
                self.server_socket = None
            self.connected = False

    def is_connected(self) -> bool:
        """Return True if a wolfHook client is currently connected and active."""
        return self.connected and self.client_socket is not None

    def _run_server(self) -> None:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(2)
            self.server_socket.settimeout(1.0)
            logger.info("WolfHookBridge listening on %s:%d", self.host, self.port)
        except Exception as exc:
            logger.warning("WolfHookBridge failed to bind to %s:%d: %s", self.host, self.port, exc)
            self.running = False
            return

        while self.running:
            try:
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            logger.info("WolfHook connection attempt from %s", addr)
            if not self._handle_handshake(conn):
                try:
                    conn.close()
                except Exception:
                    pass
                continue

            with self.lock:
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except Exception:
                        pass
                self.client_socket = conn
                self.connected = True

            self._handle_client_loop(conn)
            
            with self.lock:
                if self.client_socket == conn:
                    self.client_socket = None
                    self.connected = False
            try:
                conn.close()
            except Exception:
                pass

    def _handle_handshake(self, conn: socket.socket) -> bool:
        try:
            conn.settimeout(3.0)
            raw_data = conn.recv(4096)
            if not raw_data:
                return False
            request_text = raw_data.decode("latin1")
            
            # Find Sec-WebSocket-Key
            key = None
            for line in request_text.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
                    break

            if not key:
                return False

            accept_val = base64.b64encode(hashlib.sha1(key.encode("latin1") + WS_MAGIC_GUID).digest()).decode("latin1")
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
            )
            conn.sendall(response.encode("latin1"))
            conn.settimeout(None)
            return True
        except Exception as exc:
            logger.debug("Handshake failed: %s", exc)
            return False

    def _handle_client_loop(self, conn: socket.socket) -> None:
        conn.settimeout(0.5)
        # Initial identification query
        threading.Thread(target=self._initial_sync, daemon=True).start()
        
        while self.running:
            try:
                message = self._read_frame(conn)
                if message is None:
                    # Connection closed or EOF
                    break
                self._dispatch_message(message)
            except socket.timeout:
                continue
            except Exception as exc:
                logger.debug("WolfHook client loop error: %s", exc)
                break

    def _initial_sync(self) -> None:
        time.sleep(0.1)
        try:
            res = self.send_command("whoareyou")
            if res and isinstance(res.get("ret"), str):
                self.engine_name = res["ret"]
            ver_res = self.send_command("wolfVer")
            if ver_res and isinstance(ver_res.get("ret"), str):
                self.wolf_ver = ver_res["ret"]
            self.refresh_variables()
        except Exception:
            pass

    def _read_frame(self, conn: socket.socket) -> str | None:
        header = self._recv_exact(conn, 2)
        if not header:
            return None
        b1, b2 = header[0], header[1]
        opcode = b1 & 0x0F
        if opcode == 0x8:  # close frame
            return None

        is_masked = bool(b2 & 0x80)
        length = b2 & 0x7F
        if length == 126:
            ext = self._recv_exact(conn, 2)
            if not ext:
                return None
            length = struct.unpack(">H", ext)[0]
        elif length == 127:
            ext = self._recv_exact(conn, 8)
            if not ext:
                return None
            length = struct.unpack(">Q", ext)[0]

        mask = b""
        if is_masked:
            mask = self._recv_exact(conn, 4)
            if not mask:
                return None

        payload = self._recv_exact(conn, length)
        if payload is None:
            return None

        if is_masked:
            unmasked = bytearray(length)
            for i in range(length):
                unmasked[i] = payload[i] ^ mask[i % 4]
            payload = bytes(unmasked)

        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload.decode("shift_jis", errors="replace")

    def _recv_exact(self, conn: socket.socket, count: int) -> bytes | None:
        buf = bytearray()
        while len(buf) < count:
            try:
                chunk = conn.recv(count - len(buf))
                if not chunk:
                    return None
                buf.extend(chunk)
            except socket.timeout:
                if not self.running:
                    return None
                continue
            except OSError:
                return None
        return bytes(buf)

    def _send_frame(self, message: str) -> bool:
        with self.lock:
            if not self.client_socket:
                return False
            conn = self.client_socket

        data = message.encode("utf-8")
        length = len(data)
        header = bytearray([0x81])  # FIN + Text frame
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(127)
            header.extend(struct.pack(">Q", length))

        try:
            conn.sendall(bytes(header) + data)
            return True
        except Exception:
            return False

    def _dispatch_message(self, message_text: str) -> None:
        try:
            data = json.loads(message_text)
        except Exception:
            return

        req_id = str(data.get("id", ""))
        if req_id in self._pending_reqs:
            event, holder = self._pending_reqs[req_id]
            holder.append(data)
            event.set()

    def send_command(self, cmd: str, args: list[Any] | None = None, timeout: float = 3.0) -> dict[str, Any] | None:
        """Send a command JSON object to wolfHook and wait for its reply."""
        if not self.is_connected():
            return None

        self._req_counter += 1
        req_id = f"rpgrtl_{self._req_counter}_{int(time.time()*1000)}"
        payload: dict[str, Any] = {"cmd": cmd, "id": req_id}
        if args is not None:
            payload["args"] = args

        event = threading.Event()
        holder: list[dict[str, Any]] = []
        self._pending_reqs[req_id] = (event, holder)

        try:
            if not self._send_frame(json.dumps(payload, ensure_ascii=False)):
                return None
            if event.wait(timeout) and holder:
                return holder[0]
            return None
        finally:
            self._pending_reqs.pop(req_id, None)

    def refresh_variables(self) -> list[list[int]]:
        """Request all integer variables from Wolf RPG engine via genVarsJson."""
        res = self.send_command("genVarsJson")
        if res and isinstance(res.get("ret"), list):
            self.cached_vars = res["ret"]
            self.last_sync_time = time.time()
            return self.cached_vars
        return self.cached_vars

    def get_gold(self) -> int:
        """Get current player gold / 所持金 from Wolf RPG.

        In Wolf RPG standard system:
        SysVar[0] or SysVar[1] stores the player money.
        Group 0 is usually NormalVar 0..99, or SysVar.
        We check group 0 and return the detected gold.
        """
        if not self.cached_vars or (time.time() - self.last_sync_time > 2.0):
            self.refresh_variables()

        if not self.cached_vars:
            return 0

        # Check typical positions:
        # If cached_vars is a list of groups (e.g. [[var0, var1, ...], ...]):
        # Group 0 item 0 or item 1 is standard gold
        try:
            if len(self.cached_vars) > 0 and len(self.cached_vars[0]) > 0:
                # Return var[0][0] or var[0][1]
                val0 = self.cached_vars[0][0]
                val1 = self.cached_vars[0][1] if len(self.cached_vars[0]) > 1 else 0
                return val0 if val0 > 0 else (val1 if val1 > 0 else val0)
        except Exception:
            pass
        return 0

    def set_gold(self, amount: int) -> bool:
        """Set player gold to amount in Wolf RPG."""
        val = max(0, min(int(amount), 99999999))
        # Update both SysVar 0 and SysVar 1 in group 0 to guarantee coverage
        # Command protocol: {"cmd": "setVarVal", "args": [[[group, var_id, new_value], ...]]}
        updates = [
            [0, 0, val],
            [0, 1, val],
        ]
        res = self.send_command("setVarVal", args=[updates])
        self.refresh_variables()
        return res is not None and res.get("ret") != "ERR"

    def set_variable(self, group: int, var_id: int, value: int) -> bool:
        """Set a single Wolf RPG variable."""
        updates = [[int(group), int(var_id), int(value)]]
        res = self.send_command("setVarVal", args=[updates])
        self.refresh_variables()
        return res is not None and res.get("ret") != "ERR"

    def set_speed(self, speed_multiplier: float) -> bool:
        """Set game speed multiplier (e.g. 1.0, 2.0, 5.0)."""
        speed = max(0.1, min(float(speed_multiplier), 20.0))
        res = self.send_command("setSpeed", args=[speed])
        if res is not None:
            self.cached_speed = speed
            return True
        return False

    def set_noclip(self, enabled: bool) -> bool:
        """Toggle noclip (walk through walls)."""
        cmd = "setNoclipOn" if enabled else "setNoclipOff"
        res = self.send_command(cmd)
        if res is not None:
            self.cached_noclip = enabled
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Return high-level status summary for frontend."""
        return {
            "connected": self.is_connected(),
            "engine": self.engine_name,
            "version": self.wolf_ver,
            "gold": self.get_gold() if self.is_connected() else 0,
            "speed": self.cached_speed,
            "noclip": self.cached_noclip,
            "groupCount": len(self.cached_vars),
            "totalVars": sum(len(grp) for grp in self.cached_vars),
        }


# Global singleton bridge
_GLOBAL_WOLF_BRIDGE: WolfHookBridge | None = None
_BRIDGE_LOCK = threading.Lock()


def get_wolf_hook_bridge() -> WolfHookBridge:
    """Return the global WolfHookBridge instance, starting it if not active."""
    global _GLOBAL_WOLF_BRIDGE
    with _BRIDGE_LOCK:
        if _GLOBAL_WOLF_BRIDGE is None:
            _GLOBAL_WOLF_BRIDGE = WolfHookBridge()
            _GLOBAL_WOLF_BRIDGE.start()
        return _GLOBAL_WOLF_BRIDGE
