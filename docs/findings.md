# Findings

> **Anonymized for confidentiality.** Company names, figures, vendors, and
> infrastructure identifiers are replaced with neutral placeholders throughout.
> The methods, measurements, and conclusions are unaltered.

Empirical results from running this system in production. Each entry is written as a
fact plus the method that established it, because the method is the transferable part.

---

## 1. Instruction-in-context is not a control mechanism

**Observed.** The injection hook's first version ended with a line telling the model to
quote a verification token when asked. The production agent refused, explaining that the
request arrived inside injected hook output, that it treated that as data rather than
instructions, and that the pattern was worth reviewing.

**Why it was right.** Hook output is environment data, not a user turn. An agent that
honours directives arriving through a data channel by default will also honour them when
they arrive inside a document it was asked to summarize. The refusal was correct security
behaviour; the hook was the thing at fault.

**Consequence.** Injected blocks now open by stating they contain facts only and carry no
authority over user instructions. Where a value must be read back, the request comes from
the user. Verification no longer depends on the model at all: the hook writes what it
minted to disk, and the check compares the two.

**The general rule.** You cannot make an agent do something by writing an instruction into
its context. A well-behaved agent discounts it; a badly-behaved one was never a control.
Either way, instruction-by-injection is not enforcement. Removing the capability is.

---

## 2. Agents route around refusals

**Observed.** In a sandboxed run, an agent asked to commit was refused by the guard. It
then moved up three directories into a different repository and staged everything there
instead. Nothing sensitive moved (ignore rules held, and the commit itself was refused),
but the intent generalized in a way the rule did not.

**Diagnosis.** The refused capability had been specified as a verb (`git commit`) rather
than as an outcome (*modify the repository*). Blocking one spelling of an action leaves
every other spelling open.

**Fix.** The guard now refuses the *capability class* — all repository-mutating verbs —
and confines writes to a permitted subtree regardless of path shape, following symlinks
before deciding. Test coverage grew from 4 cases to 16, including the paths an escape
would actually take.

**Transferable.** When writing a rail, name the capability you are removing, not the
command you happened to think of. Then try to defeat it yourself.

---

## 3. Silent failure modes hide in the "success" path

**Observed.** A provisioning script reported success and produced nothing. The remote
script was delivered to `bash -s` over stdin; partway through, it ran `cat` to read a
payload — which consumed *the remainder of the script itself*. Bash reached end-of-input,
exited 0, and every downstream check interpreted that as a clean run.

**Fix.** Nothing in a script delivered on stdin may read stdin at runtime. Payloads now
travel as base64 literals piped from `echo`, giving each consumer its own descriptor.
The deploy path also asserts a positive marker (`PROVIDER_APPLIED ...`) rather than
inferring success from a zero exit code.

**Transferable.** Exit code 0 means "nothing raised", not "the work happened". Assert on
a positive artifact the work must have produced.

---

## 4. Isolating a vendor behaviour change

**Situation.** An agent that connected successfully at 09:18 was rejected from midday
onward with a membership error, after no change on our side.

**Method.** A four-cell matrix, holding identity, credentials, and configuration constant
while varying one dimension at a time:

| Runtime build | Origin | Result |
|---|---|---|
| built from source, main | cloud host | rejected |
| built from source, release tag | cloud host | rejected |
| vendor's own binary, run manually | residential | connects |
| vendor desktop application | residential | connects |

Two cells were executed 60 seconds apart with the same key and no application running,
which isolates origin from every other variable. A later test added a fifth cell — the
vendor's own documented plugin mechanism for remote execution — which was also rejected,
eliminating "how the process is launched" as the explanation.

**Result.** A one-line reproduction and a published upstream report, rather than a hunch.
A neighbouring control also mattered: ordinary member authentication from the same host
was unaffected, which narrowed the finding to the agent-authentication path specifically.

**Transferable.** When a platform changes underneath you, spend the first hour building
the matrix. "It broke" is unactionable; "these four cells, one variable" is a bug report
the vendor can act on and a decision input you can plan around.

---

## 5. Retrieval: what actually moved the number

Measured by replaying an 80-question golden set through the production code path.

| Intervention | Effect | Note |
|---|---|---|
| `top_k` 50 → 100 | material gain | 100 is the platform's hard maximum; requests above it are rejected |
| Replacement-style rerank | **net zero** | demoted as many relevant documents as it promoted |
| Consensus rerank | material gain | blend reranker output with the fusion order: keep promotions, damp demotions |
| Pure-OR lexical leg | **worse** than baseline | capitalized common nouns flood the results in multilingual corpora |
| AND-first ladder, OR-appended | gain | rescue behaviour without displacing precise matches |
| Filename candidates entering rerank with empty text | silent loss | give the reranker document head text, or it cannot score them |

**The measurement discipline mattered more than any single change.** An early scoring bug
(naive basename matching, which counted rendered-spreadsheet hits as misses) made the
pipeline look worse than it was and pointed tuning in the wrong direction for a day. Two
questions initially classified as "unreachable by any retrieval leg" turned out to be
scoring artifacts.

Rules adopted afterwards:

- The replay and the live answer path share **one** function. They cannot diverge.
- Every claimed improvement is replayed before it ships; the run takes ~2 minutes and
  gates deploys.
- Held-out evaluation on a corpus never used for tuning, to detect overfitting
  (0.787 → 0.872 there, versus 0.727 → 0.89 on the tuning set).

---

## 6. Cost accounting can lie in the direction that flatters you

The per-query cost accumulator over-reported reranking cost by roughly two orders of
magnitude: it charged per candidate, while the API bills per query. Because the error made
the system look *more* expensive, nobody questioned it — the bias to check numbers that
flatter you is well known, and this is the mirror-image failure. Cost figures are now
reconciled against a real invoice before being used for anything that matters.
