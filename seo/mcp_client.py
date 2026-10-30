#!/usr/bin/env python3
"""Minimal MCP stdio client — spawn a server, list its tools (with schemas) or call them.

Used by ``resolve.py --validate-live`` (live tool surface) and ``seo/pipeline.py``
(scripted data pulls through ``Session.call_tool``).

Standalone use:
    python3 seo/mcp_client.py            # dump every server's tools to seo/tool-schemas.json
    python3 seo/mcp_client.py search-console   # dump one server
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MCP_JSON = ROOT / ".roo" / "mcp.json"


def _load_servers() -> dict:
    return json.loads(MCP_JSON.read_text())["mcpServers"]


class Session:
    """One MCP stdio server process: handshake once, then list or call tools (``with Session(spec) as s:``)."""

    def __init__(self, spec: dict, timeout: float = 60.0):
        self.spec, self.timeout, self._id = spec, timeout, 2
        cmd = [spec["command"], *spec.get("args", [])]
        env = os.environ.copy()
        env.update({k: str(v) for k, v in spec.get("env", {}).items()})
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, text=True, bufsize=1,
        )
        self._q: "queue.Queue[str]" = queue.Queue()
        self._err: list[str] = []

        def reader():
            for line in self.proc.stdout:
                self._q.put(line)

        def err_reader():
            for line in self.proc.stderr:
                self._err.append(line.rstrip())

        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=err_reader, daemon=True).start()
        try:
            self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "seo-resolver", "version": "1"}}})
            self._wait(1, self.timeout)
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            self.close()
            raise

    def _tail(self, n: int = 5) -> str:
        return (": " + " | ".join(self._err[-n:])) if self._err else ""

    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _wait(self, rid: int, timeout: float) -> dict:
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("MCP response timeout" + self._tail())
            try:
                line = self._q.get(timeout=min(remaining, 0.5)).strip()
            except queue.Empty:
                if self.proc.poll() is not None and self._q.empty():  # crashed (e.g. bad credentials): fail fast
                    time.sleep(0.1)  # let the stderr reader catch up
                    raise RuntimeError(f"MCP server exited with code {self.proc.returncode}{self._tail()}")
                continue
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"MCP sent non-JSON line: {line[:200]!r}{self._tail()}") from e
            if msg.get("id") != rid:
                continue
            if msg.get("error"):
                raise RuntimeError(f"MCP error: {msg['error']}{self._tail()}")
            return msg.get("result", {})

    def _request(self, method: str, params: dict, timeout: float | None = None) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        return self._wait(self._id, timeout or self.timeout)

    def list_tools(self) -> list[dict]:
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict, timeout: float | None = None) -> dict:
        """The raw ``tools/call`` result: ``{"content": [...], "isError": bool, ...}``."""
        return self._request("tools/call", {"name": name, "arguments": arguments}, timeout)

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def list_tools(spec: dict, timeout: float = 60.0) -> list[dict]:
    """Spawn the server, do the MCP handshake, return its tools (name + inputSchema)."""
    with Session(spec, timeout) as s:
        return s.list_tools()


def dump(names: list[str] | None = None) -> dict:
    servers = _load_servers()
    out = {}
    for name, spec in servers.items():
        if names and name not in names:
            continue
        try:
            tools = list_tools(spec)
            out[name] = {t["name"]: t.get("inputSchema", {}) for t in tools}
            print(f"OK   {name}: {len(tools)} tools")
        except Exception as e:  # noqa: BLE001
            out[name] = {"__error__": str(e)}
            print(f"FAIL {name}: {e}")
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or None
    dest = HERE / "tool-schemas.json"
    data = json.loads(dest.read_text()) if (names and dest.exists()) else {}
    data.update(dump(names))  # dumping one server keeps the other servers' cached schemas
    dest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"wrote {dest.relative_to(ROOT)}")
