#!/usr/bin/env python3
"""Recompute the public scoreboard from sanitized run metadata. Standard library only."""
import collections
import json
import pathlib
import statistics

SOURCE = pathlib.Path(__file__).with_name("runs.jsonl")
ORDER = ("existing", "answer", "answer_read", "plain")
LABELS = {"existing": "Existing harness", "answer": "+ answer mode",
          "answer_read": "+ answer mode and whole-record reading", "plain": "Plain Claude"}


def summarize():
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    if len(rows) != 540:
        raise ValueError("Expected 540 exported task runs")
    seen = {(r["configuration"], r["task"], r["round"]) for r in rows}
    if len(seen) != len(rows):
        raise ValueError("Duplicate task run")
    print("| Configuration | Tasks solved / 45 | Median 10-turn conversation | Estimated cost / successful task run | Refused steps |")
    print("|---|---:|---:|---:|---:|")
    summaries = {}
    for arm in ORDER:
        runs = [r for r in rows if r["configuration"] == arm]
        tasks = collections.defaultdict(list)
        for r in runs:
            tasks[r["task"]].append(r)
        if len(tasks) != 45 or any({r["round"] for r in rs} != {1, 2, 3} for rs in tasks.values()):
            raise ValueError(f"Incomplete configuration: {arm}")
        solved_tasks = sum(sum(r["solved"] for r in rs) >= 2 for rs in tasks.values())
        successful_runs = sum(r["solved"] for r in runs)
        cost = sum(r["estimated_cost_usd"] for r in runs) / successful_runs
        chat = statistics.median(r["seconds"] for r in runs if r["turns"] == 10)
        refused = sum(r["refused_steps"] for r in runs)
        summaries[arm] = {"chat": chat, "cost": cost}
        print(f"| {LABELS[arm]} | {solved_tasks} | {chat:.0f} s | ${cost:.2f} | {refused} |")
    candidate, plain = summaries["answer_read"], summaries["plain"]
    print(f"\nConversation latency reduction vs plain: {1-candidate['chat']/plain['chat']:.1%}")
    print(f"Estimated cost reduction per successful task run: {1-candidate['cost']/plain['cost']:.1%}")


if __name__ == "__main__":
    summarize()
