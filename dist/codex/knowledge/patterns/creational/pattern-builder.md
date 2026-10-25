---
id: pattern-builder
type: pattern
title: Builder
signals:
- constructor with many optional parameters
- several overloaded constructors differing by one parameter
- object assembled in many steps at several call sites
required_evidence:
- a constructor or factory method with 5 or more parameters, or 3+ overloads, shown in the structure model
- two or more call sites pass long positional argument lists or null placeholders
- the object has optional parts or an ordered construction process
anti_signals:
- fewer than 4 parameters and no optional ones
- only one call site constructs the object
- a language feature (named/default arguments, records) already solves it
precedence: ../../precedence.md
cost: 'low-medium: one builder class mirroring the product fields'
links:
  smells:
  - smell-telescoping-constructor
  - smell-hardcoded-construction
  principles:
  - principle-srp
  - principle-kiss
  patterns: []
---

# Builder

**Intent.** Separate step-by-step construction of a complex object from its representation.

**When to use.** Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell or variation point must be cited (smell-telescoping-constructor, smell-hardcoded-construction).

**When NOT to use.** fewer than 4 parameters and no optional ones; only one call site constructs the object; a language feature (named/default arguments, records) already solves it. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** New optional fields no longer change every constructor call site.
