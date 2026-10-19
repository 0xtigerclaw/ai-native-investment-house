# Engineering findings

These findings come from implementation reviews and controlled replays. The public
examples use fictional data and omit private incident details.

## Test enforcement separately from model behavior

An agent declining a request does not show that a guard works. The model may have
declined without attempting the operation. The first demo probe sends crafted tool
calls directly to the guard and checks both denials and permitted actions.

Model-in-the-loop probes answer a different question: did the engine load the hook,
attempt the relevant tool, and honor the result in that run? Both kinds of checks are
useful, but they establish different things.

## Context is input, not enforcement

An early injection experiment asked the model to echo a verification marker from
inside the injected block. The agent treated that instruction as untrusted input.
The demo now puts the request in the user's prompt and supplies the marker as data.

That experiment does not establish that models always reject instructions in retrieved
content. It establishes why a model's compliance is the wrong place to put a guarantee.
The public marker is deterministic and inspectable, not a cryptographic attestation.

## Guard the operation and inspect alternate routes

Blocking a particular `git` verb did not cover the broader outcome of changing a
repository. The implementation work expanded checks and tested alternate execution
paths, caller identity, and approvals issued from within an agent turn.

The public demo still uses shell patterns and is intentionally limited. It illustrates
where a host can refuse a call; it does not prove that arbitrary commands cannot bypass
the policy. Production authorization belongs at the operation, with isolation and
credentials protected independently of the model.

## False refusals are defects too

An early redirect pattern treated `2>&1` as a file write and refused a harmless listing.
The guard now separates descriptor plumbing from ordinary redirects, and the direct
probe checks that the listing remains permitted.

A passing denial test is not sufficient if the same rule blocks routine work. The
evaluation export also reports refused steps: the improved configuration made more
refused attempts, despite lower overall latency. That friction remains visible.

## Verify the evaluation setup before interpreting the score

Earlier comparisons ran the wrong installation or reused conversation state. Later
runners checked executable paths, code and settings, fresh conversation identifiers,
and the intended notes before starting.

Another defect counted resumed-session cost totals repeatedly. Cost accounting now
distinguishes cumulative session reports from per-call reports. The public evaluation
labels these values as API-rate estimates.

## Finding the number is not checking the claim

A figure-presence checker detected many planted digit errors but missed known errors
formed from genuine source numbers. A correct number under the wrong label and a wrong
calculation over real inputs can both pass a presence check.

This limited where the checker was useful: a warning during proposal review, rather
than a correctness gate on every answer. The experiment is discussed in the
[case study](harness.md).

## Keep the negative results

Accumulated lessons lost to no memory in the tested replay. An evidence bank increased
tool use and cost without changing the answers in its small trial. A two-search
instruction did not reliably prevent false claims that information was absent.

Those results are part of the engineering record. They explain why the current design
favors corrections that become reviewed facts, tested code, or scoped preferences,
with each change evaluated before wider use.
