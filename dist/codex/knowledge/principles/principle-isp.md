---
id: principle-isp
type: principle
title: Interface Segregation Principle
links:
  smells: [smell-incompatible-interface, smell-fat-interface]
  principles: []
  patterns: []
---

# Interface Segregation Principle

**Intent.** Clients should not depend on methods they do not use.

**How to detect a violation.** Interfaces with many methods where implementers leave some empty or throw, clients using a small subset.

**When NOT to apply.** A cohesive interface whose every client really uses all members.

**Precedence.** Applies only under P1 (cited evidence) and P2 (KISS and evidence beat speculative SOLID); see ../precedence.md.
