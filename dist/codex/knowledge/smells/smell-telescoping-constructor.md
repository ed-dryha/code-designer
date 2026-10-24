---
id: smell-telescoping-constructor
type: smell
title: Telescoping Constructor
signals: [several constructor overloads differing by trailing parameters, 'constructor with more than 5 parameters, many optional']
links:
  smells: []
  principles: [principle-kiss]
  patterns: []
---

# Telescoping Constructor

**What it looks like.** Observable in structure-model facts: several constructor overloads differing by trailing parameters; constructor with more than 5 parameters, many optional.

**When it is NOT a smell.** A constructor with few parameters that are all required.
