# PDC — Product Development Controller

## Problem

Long-lived product work loses coherence when intent, implementation state, evidence, and recovery context live in different places. A Product Owner should be able to direct outcomes without operating Git, interpreting raw logs, or reconstructing interrupted technical work.

## Design principles

- Start from the desired product outcome, then select the lightest valid mode.
- Advance one explicit Work Focus at a time.
- Separate product intent, execution, verification, acceptance, and integration authority.
- Freeze Engineering boundaries before building.
- Fail closed when durable authority is missing or ambiguous.
- Make interruption recovery a system responsibility, not a Product Owner chore.

## Architecture

PDC combines a human-readable Skill contract with repository-backed state, deterministic validators, immutable Engineering contracts, exact candidate snapshots, independent review evidence, and journaled recovery. Explore develops understanding, Preview creates reality evidence, and Engineering produces durable deliverables under a frozen boundary.

## Mature capabilities

- Outcome-first routing across Explore, Preview, and Engineering
- One advancing Work Focus with explicit authority ownership
- Frozen contracts and controlled revision paths
- Exact deliverable identity and reproducible verification
- Separation of Builder, Controller, and Product Owner decisions
- Evidence-bound integration, closure, and continuity recovery
- Model-behavior evaluation packets with explicit assurance levels

## Product / engineering tradeoff

PDC accepts more explicit state and validation machinery in exchange for durable control, inspectability, and recoverability. Lightweight modes stay lightweight; formal Engineering earns stronger guarantees through frozen scope and evidence.

## Public / private boundary

The public repository contains the reviewed Skill package, deterministic tooling, public verification, installation and open-source project infrastructure. Private project state, internal operational evidence, private Git history and private-history regression infrastructure remain excluded. See [`../../PUBLIC_RELEASE_SCOPE.md`](../../PUBLIC_RELEASE_SCOPE.md) for the canonical boundary.

This public package is distributed under the repository's [MIT License](../../LICENSE).
