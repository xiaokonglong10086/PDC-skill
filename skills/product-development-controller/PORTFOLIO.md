# PDC — Product Development Controller

## Problem

Long-lived product work loses coherence when intent, implementation state, evidence, and recovery context live in different places. A Product Owner should be able to direct outcomes without operating Git, interpreting raw logs, or reconstructing interrupted technical work.

## Design Principles

- Start from the desired product outcome, then select the lightest valid mode.
- Advance one explicit Work Focus at a time.
- Separate product intent, execution, verification, acceptance, and integration authority.
- Freeze Engineering boundaries before building.
- Fail closed when durable authority is missing or ambiguous.
- Make interruption recovery a system responsibility, not a Product Owner chore.

## Architecture

PDC combines a human-readable Skill contract with repository-backed state, deterministic validators, immutable Engineering contracts, exact candidate snapshots, independent review evidence, and journaled recovery. Explore develops understanding, Preview creates disposable evidence, and Engineering produces durable deliverables under a frozen boundary.

## Mature Capabilities

- Outcome-first routing across Explore, Preview, and Engineering
- One advancing Work Focus with explicit authority ownership
- Frozen contracts and controlled revision paths
- Exact deliverable identity and reproducible verification
- Separation of Builder, Controller, and Product Owner decisions
- Evidence-bound integration, closure, and continuity recovery
- Model-behavior evaluation packets with explicit assurance levels

## Engineering Evidence

The package includes deterministic lifecycle tools, strict schemas and templates, package audits, a curated standalone public verification suite, exact-target review execution, authority reconciliation, and recovery checks. A technical PASS proves the contracted technical boundary; it does not silently stand in for Product Owner acceptance. See `PUBLIC_VERIFICATION.md` for the exact public test boundary.

## Product / Engineering Tradeoffs

PDC accepts more explicit state and validation machinery in exchange for durable control, inspectability, and recoverability. It avoids both process theater and implicit authority: lightweight modes stay lightweight, while Engineering earns stronger guarantees through frozen scope and evidence.

## What I Learned

Product control improves when authority is modeled as data rather than inferred from prose. Recovery must complete the original operation, not merely repair a substep. Independent verification needs an exact candidate identity, and a Product Owner-facing system should absorb technical transport and reconstruction work.

## Public / Private Boundary

This public repository contains a curated mature Skill package, supporting deterministic tooling, and standalone public verification. It excludes private project state, internal evolution notes, private regression infrastructure, private Git history, operational evidence, and unfinished work. It is a portfolio snapshot, not a live authority source, and no open-source license is granted.

