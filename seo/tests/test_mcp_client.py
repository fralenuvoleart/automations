"""Tests for seo/mcp_client.py — the stdio MCP session the pipeline uses (fake server, no network)."""
import sys
import tempfile
import time
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))
import mcp_client  # noqa: E402
from _runner import main  # noqa: E402

SERVER = r'''
import json, os, sys, time
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    m, rid = msg["method"], msg["id"]
    if m == "initialize":
        res = {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "fake"}}
    elif m == "tools/list":
        res = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
    elif m == "tools/call":
        name, args = msg["params"]["name"], msg["params"]["arguments"]
        if name == "slow":
            time.sleep(1.5)
        if name == "crash":
            print("fatal: credentials missing", file=sys.stderr, flush=True)
            sys.exit(3)
        if name == "bad":
            print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "bad args"}}), flush=True)
            continue
        res = {"content": [{"type": "text", "text": json.dumps({"tool": name, "args": args,
                                                                 "env": os.environ.get("FAKE_TOKEN")})}],
               "isError": name == "fails"}
    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}), flush=True)
'''


def _spec():
    d = tempfile.mkdtemp()
    script = Path(d) / "server.py"
    script.write_text(SERVER)
    return {"command": sys.executable, "args": [str(script)], "env": {"FAKE_TOKEN": "t0k"}}


def test_handshake_list_and_call():
    with mcp_client.Session(_spec(), timeout=10) as s:
        assert [t["name"] for t in s.list_tools()] == ["echo"]
        res = s.call_tool("echo", {"a": 1})
        assert res["isError"] is False and '"args": {"a": 1}' in res["content"][0]["text"]
        assert '"env": "t0k"' in res["content"][0]["text"]  # server env from the spec reaches the process
        assert s.call_tool("fails", {})["isError"] is True


def test_errors_and_timeouts_keep_the_session_usable():
    with mcp_client.Session(_spec(), timeout=10) as s:
        try:
            s.call_tool("bad", {})
            raise AssertionError("JSON-RPC error should raise")
        except RuntimeError as e:
            assert "bad args" in str(e)
        try:
            s.call_tool("slow", {}, timeout=0.3)
            raise AssertionError("should time out")
        except TimeoutError:
            pass
        time.sleep(1.5)  # the late answer arrives and is ignored by id
        assert s.call_tool("echo", {"b": 2})["content"][0]["text"].count('"b": 2') == 1


def test_crashed_server_fails_fast_with_its_stderr():
    with mcp_client.Session(_spec(), timeout=30) as s:
        t0 = time.time()
        try:
            s.call_tool("crash", {})
            raise AssertionError("crash should raise")
        except RuntimeError as e:
            assert "exited with code 3" in str(e) and "credentials missing" in str(e)
        assert time.time() - t0 < 5


def test_list_tools_helper():
    assert mcp_client.list_tools(_spec(), timeout=10)[0]["name"] == "echo"


if __name__ == "__main__":
    main(globals())
