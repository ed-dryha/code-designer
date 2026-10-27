# Design Doc and Decision Record Format

The design doc is `docs/design/<YYYY-MM-DD>-<feature-slug>-design.md`. The gate (`cd_gate.py`) parses every `### DR-NN <title>` heading and the first fenced `yaml` block under it.

## Doc skeleton

```
# Design: <feature>

- Feature: <one line>
- Date: <YYYY-MM-DD>
- Spec: <path to the approved spec, or none>
- Model generatedAt: <timestamp from .code-designer/structure-model.json>
- Coverage: <full | partial>; unavailable languages: <list or none>

## Triage
Verdict: <skip | light | full>
Override: none
Reasons:
- <reason from the cd_triage render>
Signals:
(json block with schema 2 fields, pasted from the cd_triage render)

## Context
<what exists today, with file and symbol references>

## Decision Records
### DR-01 <title>
(yaml block, see below)

## Chosen Design
| Kind | Name | Change | Signature |
|------|------|--------|-----------|
| class | PaymentGateway | added | interface with charge(amount) |

## Availability
| Name | Populated when | Readable when |
|------|----------------|---------------|
| regionCoverage | after the camera-side load completes | after load; nil before |

## Spec Coverage
| Spec lines | Quote | Covered by |
|------------|-------|------------|
| 3-3 | The new screen shows the point name. | DR-01 |
| 4-4 | Out of scope: editing points. | no design change: out of scope |

## Blast Radius
Scope: grep over <n> model-covered files (<languages>); the model has no call/import edges.
- pay/service.py:11 [model] `def refund(self, provider, amount):` sibling of the changed method
- pay/service.py:21 [grep] `def helper(x):` name match

## Unverified / Possible
- pay/service.py:21 reason: common-name, caller unknown
(or the sentence "None found")

## Backlog Findings Touched
- F-type-switch-a1b2c3
(or the word "None")

## Future Plans Used
- P-add-provider-a1b2c3
(optional section; or the word "None")

## Handoff
<next step: superpowers:writing-plans with this doc as Spec, or standalone note>
```

## Triage section

Paste the `render` output of `cd_triage.py` verbatim as `## Triage`: `Verdict:` (skip, light or full), `Override:` (`none`, or `forced-by-developer: "<phrase>"` only when the developer asked), `Reasons:` bullets, and the `Signals:` json block carrying `signalsSha`. The schema-2 block carries the edit list, base commit, rerun reason, cue dismissals (`not a change: <reason>`), triggers, `availabilityRequired`, `verdictUncapped` and `verdict`. The gate recomputes the block at the recorded base commit; it rejects a tampered block and any verdict that differs from the recomputed one unless a recorded force phrase is present. `--require-triage` makes the section mandatory. Sections from 0.2.0 (signals without a schema key) are still accepted under the 0.2.0 rules.

## Skip stub

When the verdict is skip, the doc is only the header lines (Feature, Date, Spec, Model generatedAt, Coverage, Triage), the `## Triage` section and `## Handoff`. No decision records, blast radius or other sections are needed and the gate accepts it. The stub also carries a `## Spec Coverage` table, and `## Availability` rows when the edits add state. A light verdict writes the blast radius, Availability rows and Spec Coverage only, with no decision records.

## Availability table

Every added field, property or dependency in the Chosen Design table needs one row: `Name | Populated when | Readable when`. Both cells must say something concrete, never a placeholder. The section is needed only when such an addition exists. "Populated when" answers who sets it and at what moment; "Readable when" answers from where it can be safely read.

## Spec Coverage table

When a spec was read, map each behavior to the design: `Spec lines | Quote | Covered by`. Lines are a range in the spec, the quote is verified against them (whitespace normalized), and Covered by is an existing `DR-NN` id or `no design change: <reason>`.

## Record schema

One yaml block per record. All fields are required except smell and variation_point (one of them is required when the verdict is adopt).

```yaml
id: DR-01
decision: <the question being decided>
evidence:
  - file: pay/service.py
    startLine: 3
    endLine: 8
    symbol: pay/service.py#PaymentService.charge
    quote: |
      if provider == "stripe":
          return stripe_charge(amount)
  - finding: F-type-switch-a1b2c3   # optional; open backlog id, needs a file citation too
  - plan: P-add-provider-a1b2c3   # optional; confirmed future plan id, needs a file citation too
candidate: pattern-strategy   # a knowledge base id, or none
smell: smell-type-switch      # must appear in the candidate pattern links.smells
variation_point: <what varies, if no smell applies>
alternatives:
  - option: do-nothing
    cost: <what keeping the code as is costs>
  - option: pattern-strategy
    cost: <what the pattern costs>
verdict: adopt                # adopt | reject | no-pattern
reason: "<why this verdict, non-empty>"
change_safety: "<which later changes stay local and which unrelated code is untouched>"
```

## Rules

- Backlog findings: an evidence entry `- finding: <id>` cites an open finding in `docs/design/backlog.md`. The id must exist and be open (unknown-finding, resolved-finding otherwise) and the record needs at least one verified `file` citation (finding-without-citation otherwise). The design may propose fixing the finding with an alternative `option: fix-finding`. Every touched id is listed in `## Backlog Findings Touched` (placed after Unverified / Possible, before Handoff), or the section says `None`.
- Future plans: a record may cite `- plan: <id>` as variation-point evidence only when the plan in `docs/design/future-plans.md` is confirmed and not skipped as stale, always together with a verified `file` citation in the same record (plan-without-citation otherwise). An inferred, done, dropped or unknown plan is rejected by the gate (plan-not-confirmed, unknown-plan, plan-excluded-stale). The plan states the variation; the code citation proves the seam exists; the plan alone never justifies a pattern. List used plan ids under `## Future Plans Used` (after Backlog Findings Touched, before Handoff), or write `None`; the section is optional.

- Blast Radius items are `- <path>:<line> [model|grep] <text>`; a backticked quote is verified on that line. See `BLAST-RADIUS.md`. Unverified items each need `reason:`.
- Quotes use block scalars (`quote: |`) so colons and quotes in code survive YAML. Copy the quote from the file span read immediately before writing.
- Every record lists a `do-nothing` alternative, written before the pattern option.
- `no-pattern` is a valid, passing verdict: set `candidate: none` and explain why a local change is enough.
- An `adopt` verdict with a candidate needs at least one citation of a symbol whose provenance in the model is tree-sitter, and a smell (or variation_point).
- Only `yaml.safe_load` is applied; keep the doc under 1 MB.
