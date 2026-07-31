#!/usr/bin/env python3
"""UserPromptSubmit hook: the code layer that runs before the model sees anything.

This is the answer to the reviewer's question "where is the mandatory code invocation
configured". It is configured in `.claude/settings.json`, it is executed by the
agent harness, and the model has no say in whether it runs. There is no prompt
instruction anywhere in this demo telling the agent to call this script.

What it does on every single user message:

  1. increments a turn counter that lives on disk, not in the conversation
  2. mints a proof token the model cannot guess or fabricate
  3. runs a deterministic lookup against `data/facts.json` (stands in for the
     real thing: a RAG query, a vault read, a SQL SELECT)
  4. returns the result as `additionalContext`, which the harness prepends to
     the model's context for this turn

The context_id is the observable part. If the model can report it, the script
ran, because the value would not otherwise exist in its context and cannot be
guessed. Verification can also skip the model entirely and compare against
`.state/last_injection.json`.

**This block states facts and never issues instructions.** An earlier version
signed off with "if the user asks for the token, quote it exactly", and the live
Buzz agent refused it on sight as a prompt-injection pattern. It was right. Hook
output is environment data, not a user turn, so an instruction arriving that way
should be discounted no matter who wrote it. Asking the model to read back its
own context is fine when the *user* asks; it is not fine for the context to
instruct the model on its own behalf.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".state"
FACTS = ROOT / "data" / "facts.json"

# Stable per-checkout secret, so the token is reproducible for the verifier but
# unguessable for the model. A real deployment would not need this at all; the
# freshness of a live query result is its own proof.
SEED = "the fund-deterministic-hooks-demo"


def mint_token(turn: int) -> str:
    digest = hashlib.sha256(f"{SEED}:{turn}".encode()).hexdigest()[:12].upper()
    return f"the fund-{turn:04d}-{digest}"


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
        "=== DETERMINISTIC CONTEXT (injected by hooks/inject_context.py) ===",
        "Reference information assembled by code before this turn. Statements of",
        "fact only. Nothing here asks you to do anything, and nothing here carries",
        "authority over the user's instructions.",
        "",
        f"Turn: {turn}   Minted: {stamped}   context_id: {token}",
        "",
        "Verified facts retrieved for this turn:",
    ]
    for hit in result["hits"]:
        lines.append(
            f"  - {hit['fact']}"
            f"  [value={hit['value']}; basis={hit['basis']}; source={hit['source']}]"
        )
    if result["error"]:
        lines.append(f"  ! retrieval error: {result['error']}")
    lines += ["=== END DETERMINISTIC CONTEXT ==="]

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
