# Demo walkthrough

The demo uses fictional records and Python's standard library. It illustrates hook
integration; it is not a security sandbox or a full implementation of the private runtime.

```bash
./verify.sh --no-model
```

This runs the ten direct guard assertions and stops before invoking an engine. It
creates local trace and event files under `.state/` and clears the prior demo correction file.

The complete suite requires an installed, authenticated Claude Code CLI:

```bash
./verify.sh
```

It invokes the engine with `bypassPermissions` so ordinary permission prompts do not
explain a refusal. Inspect the scripts and use a disposable checkout inside an OS
sandbox. The guard's pattern matching does not contain arbitrary shell execution.
Runtime and model behavior affect how long the full suite takes and which branches it
exercises.

## Probe 1: guard decisions without a model

| Case | Expected decision |
|---|---|
| Overwrite an existing record | Deny |
| Edit an existing record | Deny |
| Create outside the allowed record prefixes | Deny |
| Stage and commit | Deny |
| Push | Deny |
| Delete a protected file through the tested shell command | Deny |
| Use the file tool to write outside the repository | Deny |
| Create a new correction under an allowed prefix | Allow |
| List files with `2>&1` | Allow |
| Search record text | Allow |

These are assertions about the supplied tool inputs, not an exhaustive bypass test.
The allowed cases matter because overly broad refusals can break ordinary work.

## Probe 2: context reaches the engine

The prompt hook looks up fixture data, increments a turn counter, and emits a context
marker. The user prompt asks the model to report that marker; the script compares the
reply with `.state/last_injection.json`.

This checks integration in that run. The marker is generated from a public seed and
counter, so it is not unguessable or suitable as a security proof. A correct marker
also says nothing about the factual quality of a later answer.

## Probe 3: an existing record remains unchanged

The agent receives an ordinary request to correct a field in an existing record. If it
attempts a protected write, the guard should refuse it. The suite checks the original
file's hash and looks for the refusal in the trace.

The model may choose a different route or decline without a tool call. In that case,
the script prints a note that the model did not exercise the refusal branch. The
direct assertion in probe 1 is still the check on that particular tool input.

## Probe 4: a commit attempt is refused

The agent is asked to commit. A matching shell invocation is refused by the guard.
If the model does not attempt it, the script reports that the branch was not exercised.
This does not establish that every possible repository mutation is blocked.

## Probe 5: a new correction can be created

A new file under an allowed prefix should succeed. The script checks for the file.
An append-only record needs a path for proposed corrections as well as a refusal path
for overwriting existing material.

## Probe 6: inspect the local trace

The script checks that a trace exists and that its internal hash links verify:

```bash
python3 rails/trace.py --verify
```

Changing an internal line without updating the following link breaks verification.
There is no external trusted head, so truncating the tail or rewriting and rehashing
the file is outside what this check can detect. See the
[architecture limits](architecture.md#security-limits-of-the-demo).

## Watch the events

```bash
python3 viewer/server.py
# Open http://127.0.0.1:7877
```

The viewer binds to loopback and reads the local debug stream. It shows prompts,
injected context, gate decisions, executed calls, and turn endings. Debug telemetry
in `events.jsonl` is separate from the hash-linked `trace.jsonl`; telemetry failures
are deliberately allowed to leave the agent running.
