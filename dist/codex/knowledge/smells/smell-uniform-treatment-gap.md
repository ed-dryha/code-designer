---
id: smell-uniform-treatment-gap
type: smell
title: Uniform Treatment Gap
signals: [callers branch on whether an element is single or a group, separate code paths for leaf and container objects]
links:
  smells: []
  principles: [principle-ocp]
  patterns: []
---

# Uniform Treatment Gap

**What it looks like.** Observable in structure-model facts: callers branch on whether an element is single or a group; separate code paths for leaf and container objects.

**When it is NOT a smell.** Only one kind of element exists.
