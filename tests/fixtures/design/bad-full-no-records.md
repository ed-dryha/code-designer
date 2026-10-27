# Design: payments

Feature: payments
Date: 2026-10-27
Spec: spec.md
Model generatedAt: 2026-10-27
Coverage: python
Triage: see below

## Triage
Verdict: full
Override: none
Reasons:
- reason one
Signals:
```json
{
  "additiveOnly": false,
  "assumptionHits": [],
  "backlogFlagged": [
    {
      "id": "F-x"
    }
  ],
  "dependentFiles": {},
  "modelAvailable": true,
  "noGrammarLanguages": [
    "swift"
  ],
  "planOverlap": [],
  "signalsSha": "94d07ac15ca0313ba4000b09a2756766a27cf036d726698989a02295b3a6c915",
  "switchSites": 0,
  "touchedExisting": 1,
  "variationPoints": []
}
```

## Blast Radius

Scope: grep over model-covered files (python); the model has no call/import edges, so dependents come from model parent/child links and grep.

- pay/service.py:11 [model] `def refund(self, provider, amount):` sibling method of the changed charge
- pay/service.py:21 [grep] `def helper(x):` name match for helper

## Unverified / Possible

- pay/service.py:21 reason: common-name style match, caller unknown
