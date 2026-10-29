#!/usr/bin/env python3
"""Minimal MCP stdio client — spawn a server and list its tools (with schemas).

Used by ``resolve.py --validate-live`` to check the registry against the *live*
tool surface (names + inputSchema), not a hand-maintained manifest.

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


def list_tools(spec: dict, timeout: float = 60.0) -> list[dict]:
    """Spawn the server, do the MCP handshake, return its tools (name + inputSchema)."""
    cmd = [spec["command"], *spec.get("args", [])]
    env = os.environ.copy()
    env.update({k: str(v) for k, v in spec.get("env", {}).items()})
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, text=True, bufsize=1,
    )
    q: "queue.Queue[str]" = queue.Queue()
    err_lines: list[str] = []

    def reader():
        for line in proc.stdout:
            q.put(line)

    def err_reader():
        for line in proc.stderr:
            err_lines.append(line.rstrip())

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=err_reader, daemon=True).start()
    deadline = time.time() + timeout

    def _tail(n: int = 5) -> str:
        return (": " + " | ".join(err_lines[-n:])) if err_lines else ""

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def recv() -> dict:
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("MCP response timeout" + _tail())
            try:
                line = q.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("MCP response timeout" + _tail())
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"MCP sent non-JSON line: {line[:200]!r}{_tail()}") from e

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "seo-resolver", "version": "1"}}})
        while recv().get("id") != 1:
            pass
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        while True:
            msg = recv()
            if msg.get("error"):
                raise RuntimeError(f"MCP error: {msg['error']}{_tail()}")
            if msg.get("id") == 2:
                return msg.get("result", {}).get("tools", [])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


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
    data = dump(names)
    dest = HERE / "tool-schemas.json"
    dest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"wrote {dest.relative_to(ROOT)}")
