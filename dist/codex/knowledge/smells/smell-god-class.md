---
id: smell-god-class
type: smell
title: God Class
signals: [class with a very large number of methods or fields (e.g. more than 20 methods), field groups each used by a disjoint subset of methods, imports spanning unrelated domains]
links:
  smells: []
  principles: [principle-srp]
  patterns: []
---

# God Class

**What it looks like.** Observable in structure-model facts: class with a very large number of methods or fields (e.g. more than 20 methods); field groups each used by a disjoint subset of methods; imports spanning unrelated domains.

**When it is NOT a smell.** A large class that is a cohesive data holder or generated code.
