# Making an agent harness earn its keep

The context layer in this repository is what the agents read and write. The harness is
what runs them: a team of agents in the firm's chat rooms that answer questions over the
corpus, draft records, file documents and write code, with anything consequential
waiting for a person to approve it.

The harness was started by a colleague. This write-up covers the parts I built and what
I learned measuring them over two months. Its code is not published here; the same
anonymization as the rest of the repository applies.

## The bar: no worse than plain Claude, plus one advantage

A harness adds rules, memory, approvals and routing on top of a coding engine (Claude
Code, run headless). Each of those can make the agent slower or dumber than the engine
on its own. So the only question that matters is: on real work, does the harness beat
the plain engine with the same model?

To answer it I built a graded task set:

- 45 real tasks taken from the team's own questions, single questions and multi-turn chats.
- Three arms: plain engine, live harness, harness plus the change under test.
- Three rounds per arm, so one lucky run cannot decide anything.
- Answer keys built twice by two different models, and blind grading (the grader never
  sees which arm wrote the answer).

| Arm | Solved (of 45) | Cost per solved task |
|---|---|---|
| Plain engine | 44 | $1.05 |
| Harness as it was | 41 | about the same |
| Harness after the fixes below | 43 | $0.91 |

The fixed harness is also the fastest arm: a median of 53 s on single questions and
483 s on chats, against 813 s for the plain engine on chats.

## What I built

**Liveness.** A long agent session used to go quiet with no sign of whether it was
working, stuck or dead. Turns now report themselves, so the room can see what the agent
is doing. And an agent can no longer push changes live from its own shell: deploys go
through a person.

**Asking a person, headless.** An agent that is unsure should ask, not guess. The
engine's question tool only appears when it has a host to ask through, so in headless
mode it silently vanishes. I wired a permission hook that pauses the engine, posts the
question in the room, and feeds the person's answer back as the tool result. First live
test: the agent asked, a person answered, the turn continued 27 s later.

**Approvals in the right place.** Consequential actions stop as a pending run that shows
the whole proposal. I moved the approval gate so it sits where the action actually
happens, and made record approvals wait for the named person rather than anyone in the
room.

**Effort routing.** Not every turn needs deep reasoning. A small classifier scores each
turn and returns a confidence; the harness sets the engine's effort level from it.
Hard turns keep their effort, easy follow-ups drop to low. Same accuracy on the replay,
chats about 25% faster.

**Answer mode.** For plain questions the agent answers from the record first and only
then goes searching, instead of re-auditing everything on every turn.

**Memory, as a spec first.** I mapped 14 gaps in how the agents remember across
sessions and wrote a 10-component design. It is decided by a four-arm replay rather
than by taste.

## What the measurements taught me

1. **Tuning for speed quietly broke accuracy.** An early round of prompt changes made
   the agent much faster on a check of five key figures. It also made it confidently
   wrong on the parts the check did not cover. Speed is never the score on its own.
2. **Short tests lie; replay the real chat.** A change that won on single questions lost
   badly when replayed through a real ten-turn conversation. Every comparison now
   includes a chat replay.
3. **Low effort produces false "none" claims.** At low reasoning effort the agent says
   "there is no earn-out" when the term sits in a document it did not open. The fix is a
   rule: two receipts before any claim that something does not exist.
4. **The wins came from reading, not tools.** The tasks the plain engine solved and the
   harness missed were all cases where the agent never opened the right section. The
   fixes were about making it read the whole record, not about adding search.
5. **Check your test rig before your result.** Two comparisons were invalid because the
   rig ran the wrong install or reused old threads. There is now a preflight checklist
   before any run.

## Small engine findings (Claude Code, headless)

- The question tool is not offered in `claude -p` unless a prompt host is attached;
  a permission setting of "none" removes it entirely.
- A pre-tool hook can answer a question by returning `allow` with the answers added to
  the tool input; the model then reads it as the user's answer.
- With `--resume`, the reported cost is the session's running total, so per-turn cost is
  the last value, not the sum.

## Status

Liveness, effort routing, answer mode and the person-only record approvals run in
production. Asking a person runs on the development agents as a trial. Memory is a spec
waiting on its replay. Next is porting these ideas to open models.
