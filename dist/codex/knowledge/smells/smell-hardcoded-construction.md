---
id: smell-hardcoded-construction
type: smell
title: Hard-coded Construction
signals: [new of a concrete class inside business logic, constructor call to a concrete collaborator that tests must replace]
links:
  smells: []
  principles: [principle-dip]
  patterns: []
---

# Hard-coded Construction

**What it looks like.** Observable in structure-model facts: new of a concrete class inside business logic; constructor call to a concrete collaborator that tests must replace.

**When it is NOT a smell.** Construction of value objects or standard-library types.
