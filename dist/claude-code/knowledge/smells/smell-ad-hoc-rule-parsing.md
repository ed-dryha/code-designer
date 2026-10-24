---
id: smell-ad-hoc-rule-parsing
type: smell
title: Ad-hoc Rule Parsing
signals: [string-split or regex parsing of a small rule language in several places, grammar rules encoded as conditionals]
links:
  smells: []
  principles: [principle-ocp]
  patterns: []
---

# Ad-hoc Rule Parsing

**What it looks like.** Observable in structure-model facts: string-split or regex parsing of a small rule language in several places; grammar rules encoded as conditionals.

**When it is NOT a smell.** A one-off format parsed in one place.
