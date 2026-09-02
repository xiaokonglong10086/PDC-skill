# Lifecycle Navigation

## Operating Mode vs Lifecycle State

Before presenting status or the next action to a non-technical product owner, classify exactly one current operating mode from the **optimization objective**:

- **Explore** — reduce product-direction uncertainty.
- **Preview** — obtain real product/user evidence about a clear Primary Unknown with the smallest credible closed loop.
- **Engineering** — reliably implement, repair, or maintain sufficiently understood or approved product behavior.

This is a **classification and presentation layer**, not a new state machine. Code presence does not determine the mode, and classification alone does not mutate `workflow-state.json`, create Preview state, perform Preview -> Engineering promotion, or execute Direct Engineering transitions. Existing Engineering `workflow-state.json` remains authoritative for Engineering task status.

Use `mode-classification-and-control-card.md` for the product-owner presentation rules and technical-question routing. When the classified mode is Explore, use `outcome-directed-explore.md` for the bounded decision frame; when it is Preview, use `product-experiment-workflow.md` for the experiment loop itself.

## Recovery Order

1. Establish capabilities.
2. Read `.ai-product/project-state.json` and treat `current_change` as the Focused Change pointer only.
3. Derive the Active Change Set from every valid non-closed per-change `workflow-state.json`; derive the non-parked set by excluding `draft` and `blocked`.
4. Enforce at most one non-parked change; when one exists it must be the Focus. Repair a missing/invalid Focus only when exactly one non-parked execution truth makes recovery deterministic. Fail closed on a parked Focus conflicting with another non-parked change or on multiple non-parked changes.
5. Read the Focused Change workflow and verify its frozen contract digest when status is beyond draft.
6. Verify the implementation snapshot, review, acceptance, and integration records before trusting later states.
7. Inspect fresh Git state when implementation, focus switching, blocked resume, or integration is involved. Normal resume uses exact frozen `baseline_branch_tip_sha` equality before any snapshot materialization.
8. If all unfinished changes are parked and Focus cannot be trusted, project `unfocused`; use existing authoritative priority when unique, otherwise route one Product Owner product-priority decision.

### Outcome-Directed Explore recovery overlay

When the current optimization objective is Explore, recover existing evidence **before asking the Product Owner** to repeat known context:

1. recover the desired **Outcome** from approved project facts, roadmap, decisions, and prior learning evidence;
2. recover the current **Problem / Opportunity** separately from the **Current Bet**;
3. recover prior internal/external research, the strongest material alternative/counterevidence, and any current Riskiest Assumption / Primary Unknown;
4. continue only the cheapest credible evidence route still capable of changing the decision.

Use `outcome-directed-explore.md` for the detailed frame. If reality must answer, route to **Preview**; if the opportunity/bet is no longer worth investment, **Stop**; if behavior is sufficiently understood/approved and no material product-direction unknown remains, reclassify under the existing Engineering rules. This overlay does not create a new lifecycle state or Promotion mechanism.

### Preview recovery overlay

Preview persistence is deliberately lighter than Engineering lifecycle state. It does not add Preview statuses to `workflow-state.json`.

When the current optimization objective is Preview:

1. protect any active Engineering task first; an active frozen Engineering workflow cannot be silently converted or weakened;
2. read `.ai-product/learning-ledger.md` when present;
3. inspect `.ai-product/experiments/*/experiment-brief.md` and recover the single descriptive active experiment for the current focus;
4. read its one Primary Unknown, smallest complete user loop, meaningful evidence, Secondary Observations, current next action, and `evidence.md` state;
5. continue from recovered evidence instead of treating the latest user message as proof that the focus or stage changed.

If no active experiment exists, do not invent one from stale notes. If multiple active experiments conflict with the single-focus rule, resolve that inconsistency before continuing.

## Stage Signals

| Stage | Required evidence | Next action |
|---|---|---|
| Intake | project identity, repository identity, capabilities | discovery or specification |
| Discovery | problem, user, evidence, constraints, proceed/stop decision | product definition |
| Product definition | complete observable behavior and explicit unresolved items | prototype or engineering design |
| Prototype validation | tested assumptions and result | revise, stop, or engineer |
| Engineering design | codebase-aware plan, risk boundary, decisions | task draft |
| Task contracting | strict draft validation and immutable freeze digest | implementation |
| Implementation | implementation report and durable Git review commit | bounded review |
| Review | valid PASS report | product-owner acceptance |
| Acceptance | valid accepted record | integration |
| Integration | actual repository/branch/commit, reviewed-content match, executed frozen commands, CI assurance | close and observe |
| Observation | metrics and feedback | next prioritized change |

## Required vs Optional

Always identify the required action first. Optional work cannot obscure it.

- An ADR is unnecessary for a local copy change but required for changed data ownership.
- Full E2E may be unnecessary for documentation unless the contract requires it.
- Discovery may be minimal for a known bug but cannot be skipped for an uncertain product direction.

## Scale Adaptation

- **Micro change:** product behavior, contract, focused tests, review, acceptance, integration.
- **Feature:** product spec, engineering plan, contract, layered tests, acceptance.
- **Major product area:** discovery, prototype, architecture, roadmap of separately contracted changes.

Never apply a large-project process to delay a small safe change. Never use a micro process to conceal high production risk.

## Closed-Task Rule

When a task is closed, stop reviewing it and preserve it as immutable history. New evidence, a changed baseline, or a universal stop condition creates a new linked change; closed tasks do not reopen in version 3.

## Multi-Change Closure and Focus

Closing a Focused Change never auto-refocuses parked work in PDC-4.5.2. If parked unfinished work remains, clear Focus and enter project-level `unfocused`. The Controller may immediately select a uniquely determined next focus from approved priority authority; otherwise the one next action is the Product Owner's actual priority tradeoff. This is navigation only and does not add a per-change lifecycle state or operating mode.
