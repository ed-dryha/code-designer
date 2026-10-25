---
id: pattern-interpreter
type: pattern
title: Interpreter
signals:
- string splitting, regexes or nested conditionals evaluate user-defined rules
- a small domain grammar is evaluated repeatedly
required_evidence:
- a cited ad hoc parser or evaluator for rule expressions that is edited whenever a rule form is added
- the grammar has several node kinds that are combined recursively
- rule expressions come from outside the code (config, user input) and change independently of releases
anti_signals:
- the grammar is small and stable; use a parser library or a data table instead
- rules are few enough to express as plain functions
- performance-critical evaluation where an AST walk is too slow
- Interpreter is rarely warranted; default to do-nothing or a data-driven table
precedence: ../../precedence.md
cost: 'high: grammar node class per rule plus parsing'
links:
  smells:
  - smell-ad-hoc-rule-parsing
  principles:
  - principle-kiss
  - principle-ocp
  patterns:
  - pattern-composite
  - pattern-visitor
---

# Interpreter

**Intent.** Represent a grammar as classes and evaluate sentences by walking the resulting tree.

**When to use.** Rarely. Only when every required_evidence item can be cited from the structure model (file, symbol, line span). Per [precedence.md](../../precedence.md) P1 a smell must be cited (smell-ad-hoc-rule-parsing).

**When NOT to use.** a small stable grammar (use a parser library or data table); few rules; hot paths. Per P2 and P4, KISS and do-nothing always compete: if an anti-signal holds, keep the code as is.

**Change-safety note (P5).** New rule forms become new node classes; existing rule evaluation cannot be broken by edits to a shared parser.
