---
id: smell-shotgun-surgery
type: smell
title: Shotgun Surgery
signals: [one logical change requires edits in many classes, the same constant or rule repeated across files]
links:
  smells: []
  principles: [principle-dry, principle-srp]
  patterns: []
---

# Shotgun Surgery

**What it looks like.** Observable in structure-model facts: one logical change requires edits in many classes; the same constant or rule repeated across files.

**When it is NOT a smell.** Edits that are wide only because of a mechanical rename.
