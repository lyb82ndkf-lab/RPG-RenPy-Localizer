from __future__ import annotations

"""Small, local Windows memory-search backend for the desktop workbench.

The scanner deliberately works only with a process selected from the currently
loaded game's directory.  It implements the familiar two-pass flow used for
values such as gold: search the value, change it in the game, then narrow the
same result set using the new value.
"""

import ctypes
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class MemoryScanError(RuntimeError):
    """An actionable error returned by the local memory editor."""


_IS_WINDOWS = os.name == "nt"

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
WRITABLE_PAGE_PROTECTIONS = {0x04, 0x08, 0x40, 0x80}

READ_BLOCK_SIZE = 1024 * 1024
MAX_CANDIDATES = 100_000
RESULT_PREVIEW_LIMIT = 1_000


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class _MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


class _SYSTEM_INFO(ctypes.Structure):
    # The first field is a four-byte architecture union.  Together with the
    # following DWORD page size it places min/max addresses at offset eight.
    _fields_ = [
        ("_architecture", ctypes.c_byte * 4),
        ("dwPageSize", ctypes.c_uint32),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_size_t),
        ("dwNumberOfProcessors", ctypes.c_uint32),
        ("dwProcessorType", ctypes.c_uint32),
        ("dwAllocationGranularity", ctypes.c_uint32),
        ("wProcessorLevel", ctypes.c_uint16),
        ("wProcessorRevision", ctypes.c_uint16),
    ]


@dataclass(slots=True)
class MemoryScanSession:
    session_id: str
    pid: int
    process_name: str
    value_type: str
    addresses: list[int] = field(default_factory=list)
    truncated: bool = False
    pass_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_value: int | float = 0

    def payload(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "pid": self.pid,
            "processName": self.process_name,
            "valueType": self.value_type,
            "count": len(self.addresses),
            "truncated": self.truncated,
            "pass": self.pass_count,
            "lastValue": self.last_value,
            "results": [{"address": _format_address(address)} for address in self.addresses[:RESULT_PREVIEW_LIMIT]],
        }


def _format_address(address: int) -> str:
    return f"0x{address:016X}"


class LocalMemoryScanner:
    """Read/write primitive values in one selected local game process."""

    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if _IS_WINDOWS else None
        if self.kernel32 is not None:
            # ctypes defaults function results to C ``int``.  Windows handles
            # are pointer-sized on x64, so declare the handle-returning APIs
            # explicitly before using them.
            self.kernel32.OpenProcess.restype = ctypes.c_void_p
            self.kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
            self.kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
            self.kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
            self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            self.kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
            self.kernel32.VirtualQueryEx.restype = ctypes.c_size_t
            self.kernel32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
            self.kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            self.kernel32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
            self.kernel32.GetSystemInfo.argtypes = [ctypes.c_void_p]

    @staticmethod
    def _require_windows() -> None:
        if not _IS_WINDOWS:
            raise MemoryScanError("内存修改器仅支持 Windows 桌面版。")

    @staticmethod
    def _pack_value(value: Any, value_type: str) -> bytes:
        try:
            if value_type == "int32":
                return struct.pack("<i", int(value))
            if value_type == "uint32":
                return struct.pack("<I", int(value))
            if value_type == "float32":
                return struct.pack("<f", float(value))
            if value_type == "int64":
                return struct.pack("<q", int(value))
        except (TypeError, ValueError, struct.error) as exc:
            raise MemoryScanError("数值超出所选类型可表示的范围。") from exc
        raise MemoryScanError("不支持的数值类型。")

    @staticmethod
    def _unpack_value(raw: bytes, value_type: str) -> int | float:
        formats = {"int32": "<i", "uint32": "<I", "float32": "<f", "int64": "<q"}
        try:
            return struct.unpack(formats[value_type], raw)[0]
        except (KeyError, struct.error) as exc:
            raise MemoryScanError("数值类型或内存长度无效。") from exc

    def _open_process(self, pid: int, access: int) -> int:
        self._require_windows()
        assert self.kernel32 is not None
        handle = self.kernel32.OpenProcess(access, False, int(pid))
        if not handle:
            error = ctypes.get_last_error()
            raise MemoryScanError(f"无法打开游戏进程（PID {pid}，系统错误 {error}）。请以相同权限启动游戏和本工具。")
        return int(handle)

    def _close_handle(self, handle: int) -> None:
        if self.kernel32 is not None and handle:
            self.kernel32.CloseHandle(ctypes.c_void_p(handle))

    def process_path(self, pid: int) -> Path | None:
        self._require_windows()
        assert self.kernel32 is not None
        handle = self._open_process(pid, PROCESS_QUERY_LIMITED_INFORMATION)
        try:
            size = ctypes.c_uint32(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            ok = self.kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size))
            return Path(buffer.value) if ok and buffer.value else None
        finally:
            self._close_handle(handle)

    def list_project_processes(self, root: Path, launcher: Path | None, known_pids: list[int] | None = None) -> list[dict[str, Any]]:
        """Return running EXEs located in the loaded game's tree only."""
        self._require_windows()
        assert self.kernel32 is not None
        root_text = os.path.normcase(str(root.resolve()))
        launcher_text = os.path.normcase(str(launcher.resolve())) if launcher and launcher.exists() else ""
        wanted_pids = {int(pid) for pid in (known_pids or []) if int(pid) > 0}
        snapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            raise MemoryScanError("无法枚举运行中的游戏进程。")
        rows: list[dict[str, Any]] = []
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            found = self.kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
            while found:
                pid = int(entry.th32ProcessID)
                if pid and pid != os.getpid():
                    try:
                        executable = self.process_path(pid)
                    except MemoryScanError:
                        executable = None
                    if executable:
                        full_path = os.path.normcase(str(executable))
                        in_project = full_path == root_text or full_path.startswith(root_text + os.sep)
                        if in_project or full_path == launcher_text or pid in wanted_pids:
                            rows.append({
                                "pid": pid,
                                "name": executable.name,
                                "path": str(executable),
                                "launchedByTool": pid in wanted_pids,
                            })
                entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
                found = self.kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        finally:
            self._close_handle(int(snapshot))
        return sorted(rows, key=lambda item: (not item["launchedByTool"], item["name"].lower(), item["pid"]))

    def _iter_writable_regions(self, handle: int):
        assert self.kernel32 is not None
        system_info = _SYSTEM_INFO()
        self.kernel32.GetSystemInfo(ctypes.byref(system_info))
        address = int(system_info.lpMinimumApplicationAddress or 0)
        maximum = int(system_info.lpMaximumApplicationAddress or 0)
        mbi = _MEMORY_BASIC_INFORMATION()
        while address and address < maximum:
            result = self.kernel32.VirtualQueryEx(
                ctypes.c_void_p(handle), ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
            )
            if not result:
                break
            base = int(mbi.BaseAddress or address)
            size = int(mbi.RegionSize)
            next_address = base + max(size, 0x1000)
            protection = int(mbi.Protect)
            if (
                int(mbi.State) == MEM_COMMIT
                and not (protection & PAGE_GUARD)
                and (protection & 0xFF) not in {PAGE_NOACCESS}
                and (protection & 0xFF) in WRITABLE_PAGE_PROTECTIONS
                and size > 0
            ):
                yield base, size
            if next_address <= address:
                break
            address = next_address

    def _read(self, handle: int, address: int, size: int) -> bytes | None:
        assert self.kernel32 is not None
        if size <= 0:
            return b""
        buffer = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = self.kernel32.ReadProcessMemory(
            ctypes.c_void_p(handle), ctypes.c_void_p(address), buffer, size, ctypes.byref(read)
        )
        if not ok or not read.value:
            return None
        return buffer.raw[: int(read.value)]

    def _scan_bytes(self, handle: int, needle: bytes) -> tuple[list[int], bool]:
        matches: list[int] = []
        seen: set[int] = set()
        truncated = False
        overlap = max(0, len(needle) - 1)
        for base, size in self._iter_writable_regions(handle):
            offset = 0
            carry = b""
            while offset < size:
                read_size = min(READ_BLOCK_SIZE, size - offset)
                raw = self._read(handle, base + offset, read_size)
                if raw:
                    block = carry + raw
                    index = block.find(needle)
                    while index >= 0:
                        address = base + offset - len(carry) + index
                        if address not in seen:
                            seen.add(address)
                            matches.append(address)
                            if len(matches) >= MAX_CANDIDATES:
                                truncated = True
                                return matches, truncated
                        index = block.find(needle, index + 1)
                    carry = block[-overlap:] if overlap else b""
                else:
                    carry = b""
                offset += read_size
        return matches, truncated

    def start_scan(self, session_id: str, pid: int, process_name: str, value: Any, value_type: str) -> MemoryScanSession:
        needle = self._pack_value(value, value_type)
        handle = self._open_process(pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)
        try:
            addresses, truncated = self._scan_bytes(handle, needle)
        finally:
            self._close_handle(handle)
        return MemoryScanSession(
            session_id=session_id,
            pid=int(pid),
            process_name=process_name,
            value_type=value_type,
            addresses=addresses,
            truncated=truncated,
            pass_count=1,
            last_value=self._unpack_value(needle, value_type),
        )

    def refine_scan(self, session: MemoryScanSession, value: Any) -> MemoryScanSession:
        needle = self._pack_value(value, session.value_type)
        handle = self._open_process(session.pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)
        try:
            session.addresses = [address for address in session.addresses if self._read(handle, address, len(needle)) == needle]
        finally:
            self._close_handle(handle)
        session.truncated = False
        session.pass_count += 1
        session.last_value = self._unpack_value(needle, session.value_type)
        return session

    def write_value(self, session: MemoryScanSession, address: int, value: Any) -> int | float:
        if address not in session.addresses:
            raise MemoryScanError("该地址不属于当前搜索结果。请先重新搜索。")
        raw = self._pack_value(value, session.value_type)
        handle = self._open_process(session.pid, PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION)
        try:
            assert self.kernel32 is not None
            written = ctypes.c_size_t(0)
            ok = self.kernel32.WriteProcessMemory(
                ctypes.c_void_p(handle), ctypes.c_void_p(address), raw, len(raw), ctypes.byref(written)
            )
            if not ok or int(written.value) != len(raw):
                error = ctypes.get_last_error()
                raise MemoryScanError(f"写入失败（系统错误 {error}）。")
            verified = self._read(handle, address, len(raw))
            if verified != raw:
                raise MemoryScanError("写入后校验失败，游戏可能已重置该数值。")
            return self._unpack_value(verified, session.value_type)
        finally:
            self._close_handle(handle)
