#!/usr/bin/env python3
"""PostToolUse demo hook and local hash-linked recorder.

Executed tool events and explicit guard denials are appended to trace.jsonl.
Each entry stores the hash of its predecessor. Verification checks internal
links; without a trusted external head it cannot detect tail truncation or a
complete rewrite with recomputed hashes. Serial demo use only: no write locking.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".state"
TRACE = STATE / "trace.jsonl"

GENESIS = "0" * 64


def _tail_hash() -> str:
    if not TRACE.exists():
        return GENESIS
    last = GENESIS
    for line in TRACE.read_text().splitlines():
        if line.strip():
            last = hashlib.sha256(line.encode()).hexdigest()
    return last


def record(event: str, tool: str, detail: dict, decision: str = "allow") -> dict:
    """Append one hash-chained entry. Used by this hook and by guard_vault.py."""
    STATE.mkdir(exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "tool": tool,
        "decision": decision,
        "detail": detail,
        "prev": _tail_hash(),
    }
    with TRACE.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def verify() -> int:
    """Re-walk the chain. Exit 0 if intact, 1 if any link is broken."""
    if not TRACE.exists():
        print("trace.jsonl: empty (nothing recorded yet)")
        return 0
    expected = GENESIS
    for n, line in enumerate(TRACE.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("prev") != expected:
            print(f"trace.jsonl: BROKEN at line {n} (chain does not match)")
            return 1
        expected = hashlib.sha256(line.encode()).hexdigest()
    print(f"trace.jsonl: intact, head {expected[:16]}")
    return 0


def summarise(tool: str, tool_input: dict) -> dict:
    """Keep the trace readable: identifying fields only, never whole payloads."""
    keep = ("file_path", "notebook_path", "command", "pattern", "url")
    detail = {k: tool_input[k] for k in keep if k in tool_input}
    if tool in {"Write", "Edit", "MultiEdit"} and "file_path" not in detail:
        detail["note"] = "no path in tool_input"
    return detail


def main() -> None:
    if "--verify" in sys.argv:
        sys.exit(verify())

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = payload.get("tool_name", "unknown")
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        from events import emit
        emit("exec", payload, tool=tool, **summarise(tool, payload.get("tool_input", {}) or {}))
    except Exception:
        pass
    record(
        event=payload.get("hook_event_name", "PostToolUse"),
        tool=tool,
        detail=summarise(tool, payload.get("tool_input", {}) or {}),
        decision="executed",
    )
    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
