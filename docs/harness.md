# Building a harness that earns its overhead

A headless coding engine can already read documents, use tools, and produce useful
answers. Running it as a shared service adds different requirements: keep conversations
separate, preserve identity, ask a person when necessary, recover interrupted work, and
show what happened. Each added rule also consumes context or time.

I extended a colleague's existing runtime around those requirements. This case study
covers my changes and experiments. It describes a private implementation; the public
code demonstrates only the context, guard, and trace hooks.

## Put approval where the action executes

A proposal shown in chat is useful only if every execution path checks the same
authorization. A model instruction to ask first cannot enforce that property.

I worked on a common entry point that carries the caller's identity into the runtime,
and on checks at the operation that performs the action. The approval path distinguishes
an agent from a person and checks who may approve the pending run. Changes to reviewed
records wait for the designated person.

Reviews found several ways the earlier boundaries could fail: an agent could invoke a
broader capability and attempt to approve it, an alternate command spelling could miss
a check, and an approval could execute twice. Fixes went into the shared execution and
approval paths, with regression tests for the failing cases.

The lesson was to test the whole route from caller to side effect. A guard on one
command spelling leaves other routes to the same operation untouched. Shell parsing
also remained a source of defects; pattern matching is a filter, not an isolation boundary.

## Let a headless agent ask a person

The engine's question tool depended on having a host that could receive the question.
In the tested headless setup, the tool could disappear or receive a denial without a
useful exchange in chat.

I connected the question to the conversation that started the turn:

1. The engine proposes a question or encounters an action that needs authorization.
2. The runtime records the pending exchange and posts it to the originating conversation.
3. The intended person answers through that surface.
4. The runtime validates the answer and resumes or refuses the waiting operation.

Clarification and authorization remain distinct: choosing a folder does not approve
an unrelated action. Tests covered ambiguous replies, replies from another agent,
stops followed by late answers, and recovering a question after a restart. A live
development trial completed the ask-answer-resume loop.

This is recorded behavior of the tested engine integration, rather than a promise
about every version of a vendor CLI.

## Make long turns observable and recoverable

A placeholder edited repeatedly can show progress without notifying the person who is
waiting. A silent process can also mean several different things: active work, a
permission wait, a usage limit, or a failed connection.

I added periodic status messages for long turns and explicit handling of engine usage
limits. Interrupted work and new messages can be held until the reset, with that state
surviving a transport restart. Repeated messages during a running turn get an explicit
status response.

Related changes moved long jobs into detached workers, carried the originating thread
and person into those workers, and let a new message from the same person reach a turn
already in progress. Longer engine conversations can roll into fresh context under the
same application session.

Deploy controls address another interruption source: an agent changing the installation
that is currently running its own turn. The deploy lane routes changes through controlled
operations, avoids launching another scheduled job while its predecessor awaits approval,
and checks for active work before an upgrade.

## Record what the runtime and engine actually did

I extended the ordered conversation event stream and telemetry to include model rounds,
tool steps, complete commands, turn summaries, and each call's cost. Live views and
delivery can read those events instead of guessing from a quiet process.

The migration is incomplete. Some session and run state still exists outside the event
log, and log rotation remains work to do. Calling the design fully event-sourced would
overstate the implementation.

Cost needed its own checks. In the tested plain-engine resume path, the reported cost
was cumulative within the session. Summing each turn's running total counted earlier
work repeatedly. The evaluation therefore uses the last reported total for that path,
and sums per-call costs for the harness path.

## Spend reasoning effort where it helps

On the inspected runs, much of the time between tool results and the next action was
model time. Lower effort made some follow-ups faster, but using it everywhere introduced
unsupported claims that information was absent.

I implemented configurable per-turn routing: a first-turn/follow-up rule, a typed
deep-or-light classifier with a confidence threshold, and a combined variant. The
combined variant keeps the first turn at the configured effort and lowers follow-ups
unless the classifier confidently identifies new deep work. A classifier failure falls
back to the configured effort; its confidence score is not a calibrated probability.

The runtime records the chosen effort and why it chose it. That makes routing something
to inspect and replay. The main benchmark below measures answer mode and reading
changes on top of its shared setup; it does not isolate the router's contribution.

## Separate an answer from a maintenance workflow

A question about a record was triggering a broader audit: re-check sources, reconsider
settled details, and inspect possible updates before replying. That workflow is useful
when maintaining a record and expensive when someone asks a narrow question.

Answer mode gives questions a shorter path: answer from the record, retrieve evidence
when needed, then stop. Requests to build or revise records retain the maintenance path.

The first version was faster but kept the same accuracy gap. Inspecting the misses
showed that relevant information was already present in the record and had not been
read. I changed the reading instructions to require the full record before declaring
it silent, with an additional search through it when needed. Answer mode plus that
change solved two more tasks in the full replay.

## Measure against the plain engine

The bar was to preserve answer quality while adding a useful capability or reducing
time and cost. To test it, I built a private replay set of 45 tasks, including single
questions and multi-turn conversations, with three repetitions per configuration.
Answer keys were drafted independently by two models; scoring combined code checks
and two judges that did not see configuration labels.

| Configuration | Tasks solved / 45 | Median 10-turn conversation | Estimated cost / successful task run |
|---|---:|---:|---:|
| Existing harness | 41 | 587 s | $1.04 |
| + answer mode | 41 | 542 s | $0.99 |
| + answer mode and whole-record reading | 43 | 483 s | $0.91 |
| Plain Claude, same underlying model | 44 | 813 s | $1.05 |

The improved harness approaches the plain engine's task count while reducing measured
conversation time and estimated cost. It does not meet the accuracy bar yet. The
remaining task count gap, disputed key items, and lack of human calibration matter more
than a rounded percentage improvement. [Evaluation details](evaluation.md) include the
exact scoring rule, refusal counts, and sanitized metadata.

## Test whether memory helps before adding more

The memory replay is complete: 36 tasks, four configurations, three repetitions,
432 task runs. The configurations used no lessons, the accumulated lesson file, ten
reviewed rules, or rules fetched on demand.

Across the three graders, accumulated lessons performed worse than no memory. The
smaller rule set did not meet the decision rule for beating no memory; fetching rules
on demand did not establish an improvement over injecting them. Graders disagreed on
absolute task counts, so this is evidence against shipping the tested memory approach,
not proof that memory cannot help.

The replacement direction routes a correction to the place where it can be checked:
a reviewed record update, a code change with a regression test, or a preference scoped
to the person who supplied it. Correction capture, classification, and person-scoped
preferences have a first implementation. The full route from a correction to a tested
code fix, and evidence that this loop improves future answers, remain open.

## Experiments that did not earn a place in the turn

**A source-presence check did not establish correctness.** A figure checker found
planted digit errors but missed known answer errors made from real numbers with the
wrong meaning or formula. A source containing a number does not validate the claim
made with it.

**A two-search instruction did not reliably prevent false absence claims.** Lower-effort
runs still skipped the extra search or denied information present in a source. I did
not treat the instruction as a solved control.

**An evidence bank added overhead without better answers in its trial.** A small replay
of four questions, three times per configuration, produced the same answers with about
27% more tool calls and 15% more estimated cost. The feature remained off by default.

**Early speed checks missed regressions.** A few correct figures made a short run look
successful while other parts of the answer got worse. Full answers and conversation
replays became part of the comparison.

These results changed what I chose to ship. More structure, more memory, and more
verification steps have to improve the workload they are meant to help.
