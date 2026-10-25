---
id: pattern-abstract-factory
type: pattern
title: Abstract Factory
signals:
- code constructs members of several related product families side by side
- families must be used together
required_evidence:
- two or more call sites instantiate concrete classes from the same family via new/constructor calls
- at least two concrete families (or a planned second one) exist for the same set of product interfaces
- client code mixes products and a mismatched combination is possible
anti_signals:
- only one product family exists and none is planned
- products are independent, not used together
- a single Factory Method would do
precedence: ../../precedence.md
cost: 'medium: one factory interface plus one factory and N products per family'
links:
  smells:
  - smell-hardcoded-construction
  - smell-class-explosion
  principles:
  - principle-dip
  - principle-ocp
  patterns:
  - pattern-factory-method
---

# Abstract Factory

**Intent.** Create families of related objects without naming their concrete classes.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-hardcoded-construction, smell-class-explosion).

**When NOT to use.** only one product family exists and none is planned; products are independent, not used together; a single Factory Method would do. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** Adding a new family becomes a new factory class; client code cannot accidentally mix families.
