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

## Context
<what exists today, with file and symbol references>

## Decision Records
### DR-01 <title>
(yaml block, see below)

## Chosen Design
| Kind | Name | Change | Signature |
|------|------|--------|-----------|
| class | PaymentGateway | added | interface with charge(amount) |

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

## Handoff
<next step: superpowers:writing-plans with this doc as Spec, or standalone note>
```

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

- Blast Radius items are `- <path>:<line> [model|grep] <text>`; a backticked quote is verified on that line. See `BLAST-RADIUS.md`. Unverified items each need `reason:`.
- Quotes use block scalars (`quote: |`) so colons and quotes in code survive YAML. Copy the quote from the file span read immediately before writing.
- Every record lists a `do-nothing` alternative, written before the pattern option.
- `no-pattern` is a valid, passing verdict: set `candidate: none` and explain why a local change is enough.
- An `adopt` verdict with a candidate needs at least one citation of a symbol whose provenance in the model is tree-sitter, and a smell (or variation_point).
- Only `yaml.safe_load` is applied; keep the doc under 1 MB.
