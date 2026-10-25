---
id: pattern-factory-method
type: pattern
title: Factory Method
signals:
- new ConcreteClass inside business logic
- switch on a type tag that chooses which class to instantiate
required_evidence:
- a method that instantiates a concrete class and also contains logic depending on the result, with the class cited by file:line
- a switch/if-chain on a type tag selects the class to instantiate in one or more call sites
- at least two concrete product types already exist or a second is planned
anti_signals:
- only one concrete type exists and no second is planned
- construction is trivial and never varies
- a plain constructor call in a test or composition root
precedence: ../../precedence.md
cost: 'low-medium: one creator hook and one subclass or function per variant'
links:
  smells:
  - smell-hardcoded-construction
  - smell-type-switch
  principles:
  - principle-dip
  - principle-ocp
  patterns:
  - pattern-abstract-factory
---

# Factory Method

**Intent.** Let a creator method decide which concrete class to instantiate, so callers depend on an interface.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-hardcoded-construction, smell-type-switch).

**When NOT to use.** only one concrete type exists and no second is planned; construction is trivial and never varies; a plain constructor call in a test or composition root. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Adding a variant adds a creator; existing callers and branches stay untouched.
