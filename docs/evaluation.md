# Evaluation method and limits

The main comparison was completed on 19 October 2026. It measures a document-and-record
question-answering agent. The private tasks, documents, answer keys, and model answers
are withheld; the public export contains only scoring and runtime metadata.

## Task set and configurations

The set contains 45 tasks: 38 single questions, three three-turn sequences, three
ten-turn conversations, and one two-turn sequence. Each configuration repeats every
task three times, giving 135 task runs per configuration and 540 in the final comparison.
A multi-turn task preserves context within its sequence; each repetition starts fresh.

| Export label | Configuration |
|---|---|
| `existing` | The existing harness configuration used as the baseline. |
| `answer` | Baseline plus a mode that answers questions without starting a record-maintenance workflow. |
| `answer_read` | Answer mode plus instructions to read and search the whole record before declaring information absent. |
| `plain` | Plain Claude Code with the same underlying model, access to the same commands and records, and a briefing generated from the same capability. |

The initial run compared the baseline, answer mode, and plain engine. The reading
change was then tested on known misses and replayed across all 45 tasks. This makes
it an iteration on a development set, rather than an independent held-out test.

## Scoring

Two models independently drafted keys. The final rubric contains 247 checkable items.
Code grades literal figures; two blind model judges grade the other items without
seeing the configuration labels. Judge points are averaged. Partial credit and
contradiction penalties are part of the rubric.

A task run passes when its unrounded score reaches 75% of the key's maximum points.
A task is counted as solved for a configuration if at least two of its three runs pass.
The exported `solved` boolean preserves that original decision; `score_ratio` is the
rounded display value.

**Estimated cost per successful task run** is the sum of estimated cost over all 135
runs, including failed runs, divided by the number of successful runs. It is not total
cost divided by the 45-task majority-vote score.

## Results

Run from the repository root:

```bash
python3 evaluation/summarize.py
```

| Configuration | Tasks solved / 45 | Median 10-turn conversation | Estimated cost / successful task run | Refused steps |
|---|---:|---:|---:|---:|
| Existing harness | 41 | 587 s | $1.04 | 37 |
| + answer mode | 41 | 542 s | $0.99 | 23 |
| + answer mode and whole-record reading | 43 | 483 s | $0.91 | 80 |
| Plain Claude | 44 | 813 s | $1.05 | 0 |

Conversation medians are over nine complete ten-turn sequences per configuration:
three tasks, three repetitions each. Their unrounded values are 587.2, 541.6, 483.3,
and 813.2 seconds, respectively. The candidate reduces that median by 40.6% against
plain Claude and its estimated cost per successful run by 12.9%.

The candidate's higher refusal count is unresolved friction. A refused step means the
agent attempted a command its guard would not permit and then had to continue through
another route. Faster final answers do not make those attempts disappear.

## What these numbers do not establish

- **No accuracy win or parity claim.** The candidate solves 43 tasks to the plain
  engine's 44. Three repetitions and model grading do not establish statistical
  equivalence or a general ranking.
- **No independent generalization result.** The reading change responds to failures
  already seen in this task set. A new held-out set is still needed.
- **No independently audited ground truth.** Some key items were disputed or corrected
  after source review; some relied on accepted human interpretations or computed
  values. Human calibration of the judges is incomplete. Other memory experiments
  also showed that different graders can give different absolute task counts.
- **No write-safety benchmark.** The questions asked the agents to leave records
  unchanged, and no configuration attempted a write. This does not test approval
  enforcement, record creation, or filing. Those need separate execution tests.
- **No end-to-end service latency claim.** These times describe the evaluation path,
  not every chat delivery, approval wait, or outage-recovery path.
- **No isolated attribution to effort routing or memory.** The four configurations
  isolate the answer-mode and reading changes on their shared setup. Other features
  need their own comparisons.
- **No invoice savings claim.** Cost comes from engine-reported API-rate estimates on
  a shared subscription login. In the tested resumed plain-engine path, the final
  cumulative session total is used once. Harness per-call costs are summed.

## Public export

[`evaluation/runs.jsonl`](../evaluation/runs.jsonl) contains one row per task run, with
opaque task labels, configuration, repetition, turn count, rounded score ratio, pass
status, elapsed seconds, estimated cost, tool calls, and refusal count. No prompts,
answers, company identifiers, source paths, run identifiers, or source documents are
included. Labels preserve the ability to compare the same anonymous task across arms.

The export reproduces the arithmetic of the scoreboard. It cannot independently
validate the original answers, grading, or experimental controls. It is an audit of
reported aggregation, rather than a public reproduction of the private benchmark.

## Separate memory experiment

A different replay compared four memory configurations on 36 tasks, three times each
(432 task runs). Accumulated lessons lost to no memory under all three graders. Ten
reviewed rules did not meet the decision rule for improving on no memory, and recall
on demand did not meet the rule for improving on injection. Absolute counts varied by
grader, and human calibration remained incomplete.

Those runs are separate from the 540-row export above. The result informed the move
toward reviewed records, tested fixes, and person-scoped preferences described in the
[harness case study](harness.md#test-whether-memory-helps-before-adding-more).
