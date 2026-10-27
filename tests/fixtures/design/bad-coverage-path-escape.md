# Design: payments

Spec: ../spec.md

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

## Blast Radius

Scope: grep over model-covered files (python); the model has no call/import edges, so dependents come from model parent/child links and grep.

- pay/service.py:11 [model] `def refund(self, provider, amount):` sibling method of the changed charge
- pay/service.py:21 [grep] `def helper(x):` name match for helper

## Unverified / Possible

- pay/service.py:21 reason: common-name style match, caller unknown
