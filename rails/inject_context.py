#!/usr/bin/env python3
"""UserPromptSubmit demo hook: look up fixture facts and add context.

The host invokes this through .claude/settings.json. Each invocation increments
an on-disk counter, emits a deterministic correlation marker, and returns data
as additionalContext. The public seed makes the marker reproducible, not secret
or unforgeable. Comparing it with a reply checks integration in that run.

The returned block supplies reference data rather than behavioral instructions.
Delivery alone does not ensure that a model uses the supplied facts correctly.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from events import emit  # noqa: E402  (telemetry, fail-open)
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".state"
FACTS = ROOT / "data" / "facts.json"

# Public seed for a reproducible correlation marker. This is not a secret.
SEED = "agent-governance-demo"


def mint_token(turn: int) -> str:
    digest = hashlib.sha256(f"{SEED}:{turn}".encode()).hexdigest()[:12].upper()
    return f"CTX-{turn:04d}-{digest}"


def bump_turn() -> int:
    STATE.mkdir(exist_ok=True)
    counter = STATE / "turns.json"
    turn = 0
    if counter.exists():
        try:
            turn = json.loads(counter.read_text()).get("turn", 0)
        except (json.JSONDecodeError, OSError):
            turn = 0
    turn += 1
    counter.write_text(json.dumps({"turn": turn}, indent=2))
    return turn


def lookup(prompt: str) -> dict:
    """Deterministic retrieval. Same input, same output, every time.

    Stands in for whatever the real controlled entry point is: a RAG Engine
    query, a vault fact lookup, a Postgres SELECT. The shape is what matters.
    """
    try:
        facts = json.loads(FACTS.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": f"fact store unreadable: {exc}", "hits": []}

    needle = prompt.lower()
    hits = [f for f in facts if any(k in needle for k in f["match"])]
    return {"error": None, "hits": hits or facts[:1], "store_size": len(facts)}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    prompt = payload.get("prompt", "")
    emit("prompt", payload, text=prompt[:2000])
    turn = bump_turn()
    token = mint_token(turn)
    result = lookup(prompt)
    stamped = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Written so verify.sh can assert against it without parsing the transcript.
    (STATE / "last_injection.json").write_text(
        json.dumps(
            {"turn": turn, "token": token, "at": stamped, "hits": result["hits"]},
            indent=2,
        )
    )

    lines = [
        "=== DETERMINISTIC CONTEXT (injected by rails/inject_context.py) ===",
        "Reference information assembled by code before this turn. Statements of",
        "fact only. Nothing here asks you to do anything, and nothing here carries",
        "authority over the user's instructions.",
        "",
        f"Turn: {turn}   Minted: {stamped}   context_id: {token}",
        "",
        "Fictional fixture facts retrieved for this turn:",
    ]
    for hit in result["hits"]:
        lines.append(
            f"  - {hit['fact']}"
            f"  [value={hit['value']}; basis={hit['basis']}; source={hit['source']}]"
        )
    if result["error"]:
        lines.append(f"  ! retrieval error: {result['error']}")
    lines += ["=== END DETERMINISTIC CONTEXT ==="]

    emit("inject", payload, context_id=token, turn=turn,
         block="\n".join(lines))

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "\n".join(lines),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
