#!/usr/bin/env python3
"""Debug telemetry for the enforcement chain. Feeds the local viewer.

Deliberately separate from `trace.py`: the trace is the tamper-evident hash
chain and stays minimal, while this stream is rich, ephemeral, and safe to
truncate. Nothing here is part of the audit story.

Every function fails open. Telemetry must never be the reason a hook, and
therefore the agent, stops working.

Also runnable as the Stop hook:  python3 events.py --stop
"""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".state"
EVENTS = STATE / "events.jsonl"


def emit(event: str, payload: dict | None = None, **detail) -> None:
    """Append one event line. Never raises."""
    try:
        payload = payload or {}
        STATE.mkdir(parents=True, exist_ok=True)
        line = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event,
            "session": (payload.get("session_id") or "")[:8],
            "source": "cli",
            "detail": detail,
        }
        with EVENTS.open("a") as fh:
            fh.write(json.dumps(line) + "\n")
    except Exception:
        pass  # telemetry never breaks the chain


def main() -> None:
    """Stop-hook mode: mark the end of a turn."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = {}
    emit("turn_end", payload)
    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
