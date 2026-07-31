# Deterministic hooks: where the code layer is enforced

the reviewer, 28 July: *"Configure the local Buzz/Claude flow so that every user
message runs a script, obtains a fixed value or query result, injects that
result into the model prompt, and makes the enforcement point visible."*

This directory is that, plus the two things the ask implies but does not say.

```bash
./verify.sh
```

Six probes, PASS or FAIL, about four minutes. Nothing to read first.

## The answer to the question

**The enforcement point is [`.claude/settings.json`](.claude/settings.json).**

Not a proxy. Not client-side config. Not a prompt instruction. It is a config
file read by the **agent harness**, the process that owns the conversation loop.
The harness runs the listed scripts itself, at fixed points in the loop, and
feeds the model whatever they return. The model is not asked and cannot decline.
There is no instruction anywhere in this demo telling the agent to call these
scripts, because nothing depends on it choosing to.

This matters for Buzz specifically: the Buzz desktop agent **is** a Claude Code
harness and already reads `~/.claude/settings.json` (recorded in
[`BUZZ-APP-MAP.md`](../../BUZZ-APP-MAP.md), Runtime panel). So this is not a
parallel system to build. It is configuration on the path we are already on.

Three hooks are wired:

| Hook | Script | Fires | Can it stop the agent? |
|---|---|---|---|
| `UserPromptSubmit` | [`inject_context.py`](rails/inject_context.py) | every user message, before the model reads it | no, it adds context |
| `PreToolUse` | [`guard_vault.py`](rails/guard_vault.py) | before every tool call | **yes, a `deny` means the call never happens** |
| `PostToolUse` | [`trace.py`](rails/trace.py) | after every tool call | no, it records |

## Why three and not one

The ask as written is satisfied by the first hook alone. I built all three
because injection on its own proves less than it appears to, and the gap is
exactly the one worth being honest about:

- **Injection proves the code ran.** It does not prove the model *used* the
  result. Putting text in a prompt is a strong nudge, never a guarantee.
- **The guard proves the agent can be stopped.** This is the part that is
  actually deterministic. It does not rely on the model reading, understanding,
  or cooperating, because the decision is made in a separate process and the
  tool call simply does not execute.
- **The trace proves what happened.** Hash-chained, so an entry cannot be
  removed after the fact without breaking every hash downstream.

The design rule this points at: **do not ask the agent to follow a rule when you
can remove the capability instead.** That is already Invariant 1 in
[`../../README.md`](../../README.md): agents propose, humans promote, enforced
in code rather than in prompts. The live watcher is the same idea at the other
end of the loop. This demo is the missing front half.

## What each probe shows

**Probe 1, no model involved.** Crafted payloads piped straight into the guard.
Ten cases, deny and allow, byte-identical every run. This is the mechanism, with
the model removed so there is nothing to argue about.

**Probe 2, injection.** The script mints a token the model cannot guess, then the
model is asked to repeat it. It does. The only path from the script to the
answer is the hook.

**Probe 3, the one that matters.** The agent is asked, in plain language, to
correct an out-of-date headcount in a shared vault file. An entirely reasonable
request. It tries, and the guard refuses, because that file is append-only and
corrections supersede rather than overwrite. Note the phrasing: the prompt does
**not** say "ignore your rules". That framing makes the model decline on its own,
which would prove nothing. The interesting case is the request the model has
every reason to grant.

**Probe 4, promotion.** The agent is asked to commit. It cannot. Not because it
was told not to, because the capability is refused.

**Probe 5, the control.** Creating a new dated correction file under an allowed
prefix goes through. A guard that blocks legitimate work gets switched off, so
this probe fails if the rails are too tight.

**Probe 6, the record.** Every call, including refusals, in `.state/trace.jsonl`.
Delete a line and re-run `python3 rails/trace.py --verify`: it reports which line
broke the chain.

## What this does not prove

Worth saying plainly, because the difference decides the architecture:

- It does not make the agent's *judgement* deterministic. The guard controls
  which actions are possible, not whether the valuation number is right. Human
  approval stays in the loop for exactly that reason.
- `UserPromptSubmit` guarantees the retrieval ran and the result was in context.
  It does not guarantee the model reasoned from it. If a step must be certain,
  it belongs in the validator, not in the prompt.
- These rails are per-agent-install. They travel with `settings.json`. Making
  them non-optional across the team means shipping the config, which is a
  deployment question, not a technical one.

## The live agent refused the demo, and was right

The first end-to-end test in Buzz asked the the fund agent for the token. It
declined, and explained why: the request to quote it was arriving inside a
`UserPromptSubmit` hook block, which it treated as data rather than as
instructions, and it flagged the pattern for review.

That refusal was the successful outcome of the test. The agent could only object
to `inject_vault_state.py` by name because the hook fired and delivered its
output, so injection was proven end-to-end by the very message that refused to
cooperate with it. But the objection was also correct on the merits and the hook
was wrong. Hook output is environment data, not a user turn. An instruction
arriving through a data channel is a prompt-injection pattern regardless of who
wrote it or how good their intentions were, and an agent that honours those by
default is one that honours them when they come from a poisoned document too.

Both injection hooks were rewritten to state facts and issue no instructions.
`PROOF_TOKEN` became `context_id`, ordinary request metadata. Where the demo
needs the value read back, the request now comes from the user in the probe
prompt, which is a legitimate instruction source, and never from the context
speaking on its own behalf.

The general rule, which is the same one the guard exists to serve: **you cannot
make an agent do something by writing an instruction into its context.** A
well-behaved agent discounts it and a badly-behaved one was never a control to
begin with. Either way, instruction-by-injection is not an enforcement
mechanism. Only removing the capability is.

## One thing this demo found on its own

On the first run, the agent was asked to commit, could not, and worked its way
up three directories into the live `the fund-memory` repo to run `git add -A`
there instead. Nothing confidential moved: `.gitignore` held, and the commit
itself was refused. But it is a clean illustration of the reviewer's point about agents
operating over multiple turns against shared state, found by accident, in a
sandbox, within an hour of building the sandbox.

Two fixes went in as a result. `git add` joined the refused verbs, because the
capability to remove was "modify the repository", not "run the one verb I
happened to think of". And the guard now refuses any write outside this
directory, so running `verify.sh` cannot touch anything on your machine.

## Layout

```
.claude/settings.json   THE ENFORCEMENT POINT. Read by the harness, not the model.
rails/inject_context.py UserPromptSubmit: deterministic retrieval into context
rails/guard_vault.py    PreToolUse: the rail that can refuse a tool call
rails/trace.py          PostToolUse: hash-chained audit log (--verify to check)
data/facts.json         stands in for the real retrieval backend
vault/                  a miniature append-only vault to act against
verify.sh               the six probes
.state/                 counters, trace, last injection (regenerated, gitignored)
```

## Mapping to production

| Demo | Live |
|---|---|
| `data/facts.json` lookup | Cloud Run MCP retrieval against the RAG corpus |
| `guard_vault.py` invariants | the same invariants, plus `contracts/fact_contract.py` on content |
| `trace.jsonl` | proposal and approval history, already in the vault's git log |
| approver is a shell script | approver is a pubkey reaction, executed by `watcher/` |

The valuation-page workflow splits along the same seam. Steps 2 to 6 of the reviewer's
sequence (review priors, propose sources, ask, draft, revise) are judgement, and
stay with the agent and a human. Steps 7 to 9 (validate, publish, sync) are
gates, and belong in code: `fact_contract.py` and the watcher already are those
gates. What is still missing is not mechanism, it is the contract: the agreed
input and output shape of a valuation page, and one known-good FY2024 page to
validate against.
