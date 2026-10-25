# Design: payments

## Decision Records

### DR-01 Select provider

```yaml
id: DR-01
decision: How to select the payment provider
evidence:
  - file: ../x
    startLine: 1
    endLine: 1
candidate: pattern-strategy
smell: smell-type-switch
alternatives:
  - option: do-nothing
    cost: keep the if chain; each provider edits two methods
  - option: pattern-strategy
    cost: one interface plus one class per provider
verdict: adopt
reason: "Same provider switch repeats in charge and refund with 3 branches."
change_safety: "Adding a provider touches one new class only."
```

