#!/usr/bin/env python3
"""PreToolUse hook: the rail. Runs before every tool call and can refuse it.

Injecting context proves code RAN. It does not prove the agent BEHAVED. This
script is the part that proves the second thing, and it is a different
mechanism: the harness asks this script for permission before it executes a
tool, and a `deny` here means the tool call never happens. The model is not
consulted. It cannot retry its way past it, and a user telling it to "ignore
the rules" changes nothing, because the instruction and the enforcement live in
different processes.

The rules encoded here are the same invariants the live watcher enforces
(see ../../README.md, Invariants 1 and 2):

  1. agents propose, humans promote  -> no git commit / push / tag from the agent
  2. append-only vault               -> may create NEW files under the allowed
                                        prefixes, may never modify or delete an
                                        existing one

Everything else is allowed. The point is not to lock the agent down, it is to
put the few operations that must not be left to judgement behind code.
"""

from __future__ import annotations

import json
import pathlib
import re
import shlex
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from trace import record  # noqa: E402  (sibling module, not the stdlib `trace`)

ROOT = pathlib.Path(__file__).resolve().parent.parent
VAULT = (ROOT / "vault").resolve()
ALLOWED_NEW_PREFIXES = ("02-companies/", "05-tasks/")

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Shell verbs that reach the vault or the git remote behind the file tools.
# `add` is in this list because of an actual incident: on the first run of this
# demo the agent was asked to commit, could not, and worked its way up three
# directories into the live repo and staged the whole tree instead. Nothing
# confidential moved (gitignore held, and the commit itself was refused) but the
# lesson stands: name the capability you are removing, not the one verb you
# happened to think of.
GIT_FORBIDDEN = re.compile(
    r"\bgit\s+(commit|push|tag|add|reset|checkout|restore|merge|rebase|stash|clean|rm|mv)\b"
)
# Deciding whether a shell command mutates anything is the fiddly part, and the
# first version of this file got it wrong: the pattern `>>?\s*\S` matched the
# `2>&1` in `ls vault/ 2>&1` and refused a read-only listing. A guard that
# blocks harmless work gets switched off, so this is now done in two explicit
# steps: strip fd plumbing, then look for a real write.
FD_NOISE = re.compile(r"\d*>\s*&\s*\d+|\d>\s*/dev/null|&>\s*/dev/null")
WRITE_REDIRECT = re.compile(r"(?<![0-9&])>>?\s*[^&\s]")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\|")
MUTATING_VERBS = {
    "rm", "mv", "cp", "tee", "truncate", "shred", "install", "chmod", "chown",
    "mkdir", "touch", "dd", "ln", "rmdir", "rsync",
}
SED_IN_PLACE = re.compile(r"\bsed\b[^|;&]*\s-i\b")


# Set by main() so deny() can name the tool it refused in the audit trail.
CURRENT = {"tool": "unknown", "input": {}}


def deny(reason: str) -> None:
    """Refuse the tool call. The harness enforces this, not the model."""
    record(
        event="PreToolUse",
        tool=CURRENT["tool"],
        detail={"reason": reason, **_identifying(CURRENT["input"])},
        decision="DENIED",
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
                "systemMessage": f"BLOCKED by guard_vault.py: {reason}",
            }
        )
    )
    sys.exit(0)


def allow() -> None:
    print(json.dumps({}))
    sys.exit(0)


def _identifying(tool_input: dict) -> dict:
    keep = ("file_path", "notebook_path", "command")
    return {k: tool_input[k] for k in keep if k in tool_input}


def touches_vault(path_str: str) -> bool:
    if not path_str:
        return False
    try:
        candidate = pathlib.Path(path_str)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        return VAULT == candidate.resolve() or VAULT in candidate.resolve().parents
    except (OSError, RuntimeError):
        return False


def outside_demo(path_str: str) -> bool:
    """True if the path escapes this demo directory entirely."""
    if not path_str:
        return False
    try:
        candidate = pathlib.Path(path_str)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        candidate = candidate.resolve()
        return ROOT != candidate and ROOT not in candidate.parents
    except (OSError, RuntimeError):
        return False


def check_file_write(tool: str, tool_input: dict) -> None:
    path_str = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

    if outside_demo(path_str):
        deny(
            f"Containment: '{path_str}' is outside this demo directory. The demo "
            "writes nowhere but its own tree, so running it cannot touch anything "
            "on your machine."
        )

    if not touches_vault(path_str):
        allow()

    target = pathlib.Path(path_str)
    if not target.is_absolute():
        target = ROOT / target
    target = target.resolve()
    rel = target.relative_to(VAULT).as_posix()

    if tool != "Write":
        deny(
            f"Invariant 2 (append-only vault): '{rel}' may not be modified in place. "
            "Supersede it with a new dated file instead."
        )

    if target.exists():
        deny(
            f"Invariant 2 (append-only vault): '{rel}' already exists. "
            "The agent may create new files, never overwrite them."
        )

    if not rel.startswith(ALLOWED_NEW_PREFIXES):
        deny(
            f"Invariant 2 (append-only vault): new files are confined to "
            f"{' or '.join(ALLOWED_NEW_PREFIXES)}; '{rel}' is outside both."
        )

    allow()


def mutates(command: str) -> bool:
    """Does this shell command write anything? Read-only commands pass through."""
    cleaned = FD_NOISE.sub(" ", command)
    if WRITE_REDIRECT.search(cleaned) or SED_IN_PLACE.search(cleaned):
        return True
    for segment in SEGMENT_SPLIT.split(cleaned):
        words = segment.strip().split()
        # Skip `cd x &&`-style prefixes and env assignments to reach the verb.
        for word in words:
            if word in {"cd", "sudo", "env", "nohup"} or "=" in word.split("/")[0]:
                continue
            if word in MUTATING_VERBS:
                return True
            break
    return False


def check_bash(tool_input: dict) -> None:
    command = tool_input.get("command", "")

    if GIT_FORBIDDEN.search(command):
        deny(
            "Invariant 1 (agents propose, humans promote): the agent holds no "
            "commit or publish capability. Only the watcher commits, and only on "
            "an approver reaction. Post a proposal instead."
        )

    if not mutates(command):
        allow()

    # A mutating shell command: check every token that looks like a path.
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for raw in tokens:
        token = raw.strip("'\"")
        if touches_vault(token):
            deny(
                "Invariant 2 (append-only vault): mutating the vault through the "
                f"shell is blocked too ('{token}'). The file tools are not the "
                "only door, so the guard does not only watch the file tools."
            )
        if ("/" in token or token.startswith("..")) and outside_demo(token):
            deny(
                f"Containment: this command reaches '{token}', outside the demo "
                "directory. Read-only commands are fine anywhere; mutating ones "
                "stay inside this tree."
            )
    allow()


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        allow()

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    CURRENT["tool"], CURRENT["input"] = tool, tool_input

    if tool in WRITE_TOOLS:
        check_file_write(tool, tool_input)
    elif tool == "Bash":
        check_bash(tool_input)
    allow()


if __name__ == "__main__":
    main()
