# Design: payments

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
candidate: pattern-strategy
smell: smell-type-switch
alternatives:
  - option: do-nothing
    cost: keep the if chain; each provider edits two methods
  - option: pattern-strategy
    cost: one interface plus one class per provider
verdict: adopt
reason: ""
change_safety: "Adding a provider touches one new class only."
```

