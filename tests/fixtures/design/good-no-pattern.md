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
candidate: none
alternatives:
  - option: do-nothing
    cost: none
verdict: no-pattern
reason: "Only the refund path branches; a local conditional is simpler."
change_safety: "Adding a provider touches one new class only."
```

