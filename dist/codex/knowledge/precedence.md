# Precedence Rules

Skills load this document first. When guidance in a pattern, principle or smell entry conflicts with a rule here, the rule here wins.

P1. No pattern without a cited smell or variation point. Every pattern proposal must point at real code evidence (file, symbol, line span from the structure model) showing the smell or the axis along which the code must vary.
P2. KISS and evidence outrank speculative SOLID. A principle is applied only to a violation that the code shows today or a future change that is actually planned, never to a hypothetical one.
P3. Evidence marked inferred (provenance agent, or inferred future plans) cannot be the sole justification for a pattern. At least one verified, extractor-backed citation is required. This is unchanged; triage caps the verdict at light when no touched file has extractor coverage, because no pattern can then be justified.
P4. Do-nothing ("no pattern, keep it simple") is always a candidate alternative and must be weighed explicitly against every proposal.
P5. Every proposal states its change-safety consequence: what later change becomes safer, and what unrelated code can no longer break.
