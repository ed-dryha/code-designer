# Design: payments

Feature: payments
Date: 2026-10-27
Spec: spec.md
Model generatedAt: 2026-10-27
Coverage: python
Triage: see below

## Triage
Verdict: light
Override: none
Reasons:
- reason one
Signals:
```json
{
  "additiveOnly": false,
  "assumptionHits": [],
  "backlogFlagged": [],
  "dependentFiles": {
    "pay/service.py#PaymentService": {
      "kind": "modify",
      "nonTest": 2,
      "total": 2
    }
  },
  "modelAvailable": true,
  "noGrammarLanguages": [
    "swift"
  ],
  "planOverlap": [],
  "signalsSha": "bf0d30ab803d2f8f99ddc5755c817bae74a6eb210df63e10157efee6a7a452a8",
  "switchSites": 0,
  "touchedExisting": 1,
  "variationPoints": []
}
```

## Decision Records

### DR-01 Select provider

```yaml
id: DR-01
decision: How to select the payment provider
evidence:
  - file: pay/service.py
    startLine: 3
    endLine: 8
    symbol: pay/service.py#PaymentService.charge
    quote: |
      if provider == "stripe":
          return stripe_charge(amount)
candidate: none
alternatives:
  - option: do-nothing
    cost: none
verdict: no-pattern
reason: "Only the refund path branches; a local conditional is simpler."
change_safety: "Adding a provider touches one new class only."
```

### DR-02 Select provider

```yaml
id: DR-02
decision: How to select the payment provider
evidence:
  - file: pay/service.py
    startLine: 3
    endLine: 8
    symbol: pay/service.py#PaymentService.charge
    quote: |
      if provider == "stripe":
          return stripe_charge(amount)
candidate: none
alternatives:
  - option: do-nothing
    cost: none
verdict: no-pattern
reason: "Only the refund path branches; a local conditional is simpler."
change_safety: "Adding a provider touches one new class only."
```

### DR-03 Select provider

```yaml
id: DR-03
decision: How to select the payment provider
evidence:
  - file: pay/service.py
    startLine: 3
    endLine: 8
    symbol: pay/service.py#PaymentService.charge
    quote: |
      if provider == "stripe":
          return stripe_charge(amount)
candidate: none
alternatives:
  - option: do-nothing
    cost: none
verdict: no-pattern
reason: "Only the refund path branches; a local conditional is simpler."
change_safety: "Adding a provider touches one new class only."
```

## Blast Radius

Scope: grep over model-covered files (python); the model has no call/import edges, so dependents come from model parent/child links and grep.

- pay/service.py:11 [model] `def refund(self, provider, amount):` sibling method of the changed charge
- pay/service.py:21 [grep] `def helper(x):` name match for helper

## Unverified / Possible

- pay/service.py:21 reason: common-name style match, caller unknown
