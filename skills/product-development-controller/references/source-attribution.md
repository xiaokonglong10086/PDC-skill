# Source Attribution and Adaptation Map

This skill is an original synthesis. It does not redistribute third-party repositories or copy their complete Skill files. It adapts workflow mechanisms and rewrites instructions for the user's ChatGPT-controller / coding-agent / product-owner collaboration model.

All four primary repositories below are distributed under the MIT License as of the research date, 2026-08-05.

## BMad Method

Repository: https://github.com/bmad-code-org/BMAD-METHOD

Adapted mechanisms:

- artifact-based workflow orientation;
- distinguish required next work from optional work;
- completion detection from outputs plus explicit user statements;
- show only relevant next actions;
- scale planning depth to project complexity.

Not adopted:

- large persona catalog;
- party mode;
- module-specific command menus;
- requirement to run each role in separate user-managed sessions.

## GitHub Spec Kit

Repository: https://github.com/github/spec-kit

Adapted mechanisms:

- specification before implementation;
- constitution/principles gate;
- Spec → Plan → Tasks → Implement artifact chain;
- prioritized user scenarios with independent tests;
- Given/When/Then acceptance scenarios;
- explicit clarification markers, edge cases, assumptions, and measurable success;
- codebase-aware technical plan and exact project structure.

Not adopted:

- implementing all tasks in one invocation;
- optional testing default. This skill requires tests according to the frozen risk-based contract.

## OpenSpec

Repository: https://github.com/Fission-AI/OpenSpec

Adapted mechanisms:

- one change directory per independently trackable change;
- exploration before proposal when requirements are unclear;
- planning artifacts can be deliberately updated when implementation reveals contradictions;
- deterministic scaffolding and state files;
- verification across completeness, correctness, and coherence;
- archive/close completed changes.

Not adopted:

- verification warnings that never block. This skill distinguishes contracted blockers, universal stop conditions, and non-blocking findings.

## Superpowers

Repository: https://github.com/obra/superpowers

Adapted mechanisms:

- exact, bite-sized implementation plans;
- isolated Git worktrees;
- RED-GREEN-REFACTOR for behavior changes;
- fresh evidence before completion claims;
- independent review of agent output;
- explicit branch finishing and integration checks;
- skill behavior testing through pressure scenarios.

Not adopted:

- automatic multi-subagent orchestration;
- mandatory frequent commits inside every micro-step;
- instructions that assume the coding agent is also the workflow controller.

## Google Engineering Practices

Source: https://google.github.io/eng-practices/review/reviewer/standard.html

Adapted mechanisms:

- favor approval when a change improves system health and meets requirements;
- do not demand perfection;
- mark polish and educational comments as optional;
- facts and engineering evidence outrank preference.

## GitHub Pull Request Guidance

Source: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/incorporating-feedback-in-your-pull-request

Adapted mechanism:

- track out-of-scope review feedback in a separate issue instead of expanding the current change.

## C4 and MADR

Sources:

- https://c4model.com/
- https://adr.github.io/madr/

Adapted mechanisms:

- use minimal system-context and container/runtime views;
- record consequential decisions with context, options, outcome, consequences, and confirmation.
