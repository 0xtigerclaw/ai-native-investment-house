#!/usr/bin/env python3
"""hook-viewer: watch the enforcement chain fire, live.

    python3 server.py            then open http://127.0.0.1:7877

Tails the repo's .state/events.jsonl (written by the rails) and streams
it to the browser over SSE. Stdlib only, binds loopback only, reads only.

Routes:
    /         the UI
    /events   SSE: replays the last ~100 events, then tails the file
    /status   one-shot JSON: chain verification + last injection + config path
"""

from __future__ import annotations

import http.server
import json
import os
import pathlib
import socketserver
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent                      # viewer/ lives one level below the repo root
STATE = REPO / ".state"                 # where rails/ write trace + events
EVENTS = STATE / "events.jsonl"
HOOKS = REPO / "rails"
PORT = 7877
REPLAY = 100


def chain_status() -> dict:
    try:
        out = subprocess.run(
            ["python3", str(HOOKS / "trace.py"), "--verify"],
            capture_output=True, text=True, timeout=10,
        )
        return {"ok": out.returncode == 0, "text": out.stdout.strip()}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "text": f"verify failed to run: {exc}"}


def last_injection() -> dict:
    try:
        return json.loads((STATE / "last_injection.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):  # keep the terminal quiet
        pass

    def _head(self, ctype: str, extra: dict | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path == "/":
            body = (HERE / "index.html").read_bytes()
            self._head("text/html; charset=utf-8", {"Content-Length": str(len(body))})
            self.wfile.write(body)
        elif self.path == "/status":
            body = json.dumps({
                "chain": chain_status(),
                "last_injection": last_injection(),
                "enforcement_point": ".claude/settings.json",
                "events_file": str(EVENTS),
            }).encode()
            self._head("application/json", {"Content-Length": str(len(body))})
            self.wfile.write(body)
        elif self.path == "/events":
            self._sse()
        else:
            self.send_error(404)

    def _sse(self) -> None:
        self._head("text/event-stream", {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })
        try:
            fh = None
            if EVENTS.exists():
                lines = EVENTS.read_text().splitlines()
                for line in lines[-REPLAY:]:
                    if line.strip():
                        self.wfile.write(f"data: {line}\n\n".encode())
                self.wfile.flush()
                fh = EVENTS.open()
                fh.seek(0, os.SEEK_END)
            beat = time.monotonic()
            while True:
                if fh is None and EVENTS.exists():
                    fh = EVENTS.open()  # file appeared after we started
                line = fh.readline() if fh else ""
                if line:
                    if line.strip():
                        self.wfile.write(f"data: {line.strip()}\n\n".encode())
                        self.wfile.flush()
                    continue
                if time.monotonic() - beat > 15:  # keep proxies awake
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    beat = time.monotonic()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser tab closed


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    with Server(("127.0.0.1", PORT), Handler) as srv:
        print(f"hook-viewer on http://127.0.0.1:{PORT}  (events: {EVENTS})")
        srv.serve_forever()


if __name__ == "__main__":
    main()
