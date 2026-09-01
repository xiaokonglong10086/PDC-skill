# Architecture v2 Kernel

## Purpose

Use this reference for the stable PDC control model that applies across software, Skills, Agents, automations/workflows, prototypes, internal tools, and hybrid digital deliverables.

Keep the kernel small. Object-specific methods belong in Development Profiles, specialist Skills, platform capabilities, or implementation details.

## Product job

PDC is a development control system for a non-technical or weakly technical Product Owner.

Start from the **Outcome** the Product Owner wants, not from an assumed implementation form. The Product Owner may begin before knowing whether the right deliverable is software, a Skill, an Agent, an automation, a prototype, an internal tool, a hybrid, an existing product to reuse, or no new build at all.

Architecture principle:

> **Wide entry. Narrow kernel. Strict delivery.**

## Five stable kernel concepts

### 1. Outcome

The result worth achieving plus approved product intent and authoritative constraints.

Outcome is above implementation form. A proposed deliverable is a **Current Bet** until evidence or an approved decision makes that form appropriate.

### 2. Work

A durable line of development activity directed toward an Outcome.

Several unfinished Work items may exist, but within one PDC-controlled project there is exactly one **advancing Work Focus** at a time.

Non-Focus Work may be recovered, inspected, compared, researched, or safely preserved. It must not silently advance in the background.

### 3. Mode

Exactly one current optimization mode applies to the focused Work:

- **Explore** — reduce material direction/domain/product uncertainty fastest.
- **Preview** — obtain credible reality evidence about a defined uncertainty with the smallest credible loop.
- **Engineering** — reliably construct, repair, maintain, verify, or deliver sufficiently understood/approved behavior.

Mode follows the current optimization objective, not code presence or deliverable type.

Do not add a fourth mode for research, communication, Skills, Agents, automations, or unfamiliar domains.

### 4. Control Decision

The Controller chooses the **one required next action** that most efficiently advances the Outcome while respecting authority, evidence, risk, reversibility, cost, and the current Mode.

Use the lowest-cost credible route. Do not insert a ceremony merely because more information could exist.

### 5. Evidence & Authority

A claim advances only with evidence appropriate to that claim, and PDC preserves where authoritative truth actually lives.

Do not treat chat memory, Builder assertion, file existence, or Product Owner enthusiasm as proof of a claim they cannot establish.

## Role boundaries

### Product Owner

Owns:

- desired Outcome and product intent;
- product behavior and scope;
- priorities between meaningful Outcomes;
- material product/business tradeoffs;
- acceptable ordinary-risk tradeoffs;
- final product-visible acceptance.

The Product Owner does not need to decide routine technical methods, frameworks, validators, schemas, Git mechanics, or specialist correctness.

### Controller

Owns:

- recovery of reliable project context;
- independent evaluation of Product Owner proposals;
- distinguishing facts, evidence, assumptions, Current Bets, and unknowns;
- choosing Mode and the next credible route;
- ordinary technical/workflow control decisions;
- bounded architecture and completion-boundary design;
- delegation to Builders, specialist Skills, tools, or qualified specialists;
- evidence review and lifecycle/control-state advancement;
- continuity and translation of technical reality into product meaning.

A Product Owner proposal is important input, not automatic truth. Challenge material weaknesses, unsupported decision-driving assumptions, hidden cost/risk, or materially better alternatives. Do not manufacture disagreement.

### Builder

A **Builder** executes bounded work using the appropriate tool, agent, platform, Skill, or human implementation capability.

A Coding Agent is one Builder type for repository-backed Software/PDC Engineering.

The Builder may report contradictions and implementation facts. It cannot silently redefine product intent, expand frozen scope, become the sole correctness authority, or approve its own work.

### Specialist

Qualified specialist judgment owns non-overridable correctness boundaries such as security, authorization, tenant isolation, sensitive data, compliance, irreversible migration, deployment safety, or comparable professional risk.

Do not ask the Product Owner to guess specialist correctness.

## Four authority domains

### Intent authority

Sole owner of:

- approved Outcome/product intent;
- user-visible behavior and scope;
- priorities and Product Owner intent decisions;
- frozen Engineering completion-boundary content, version, and immutable identity.

### Learning authority

Owns:

- observations;
- evidence-backed learning;
- rejected hypotheses;
- unresolved material unknowns;
- learning provenance.

Learning may justify a later Intent revision. It cannot silently mutate frozen Intent.

### Deliverable Reality authority

Owns or references the actual artifact/runtime/configuration identity and technical/behavior evidence supporting claims about that reality.

The concrete authority may be Git, a platform-native version/configuration, a deployed runtime, a package, or another profile-specific source.

### Work-control authority

Owns:

- unfinished/parked Work;
- the advancing Work Focus;
- Mode/control position;
- lifecycle/review/acceptance/delivery/closure position;
- a reference/projection to the frozen Engineering completion boundary owned by Intent authority.

Do not maintain competing mutable copies of the same completion truth.

## Engineering completion law

Engineering is the strict guarantee zone regardless of deliverable type.

When PDC claims Engineering completion:

1. intended behavior and completion boundary are explicit enough to review;
2. once frozen, completion criteria do not silently move;
3. Builder implements the frozen work and cannot redefine intent;
4. Builder cannot be the sole correctness authority;
5. evidence binds the actual artifact/runtime/version under review;
6. technical PASS and Product Owner visible acceptance are distinct;
7. causally applicable specialist/safety correctness may stop work;
8. unrelated historical debt and optional improvements cannot move the frozen finish line;
9. accepted work advances to delivery/integration or an explicit blocker;
10. closed history is durable and is not silently rewritten;
11. another Controller/session can recover the boundary, deliverable identity, evidence, acceptance, delivery state, and closure without relying on chat memory.

A Development Profile may change the technical mechanism, but not weaken this promise.

## Control loop

For the focused Work:

1. recover authoritative Outcome, current Work, evidence, decisions, and actual deliverable state;
2. identify material uncertainty or missing authority without asking the Product Owner to repeat recoverable facts;
3. classify exactly one Mode;
4. choose the lowest-cost credible route that can resolve the current control need;
5. choose exactly one required next action and its real responsible role;
6. execute/delegate through the appropriate Profile, Builder, specialist Skill/tool, or qualified specialist;
7. record evidence in the correct authority domain;
8. advance only when the evidence/decision required for that claim exists.

## Adaptive Product Owner collaboration

The communication outcome is:

> **Maximize the Product Owner's correct understanding and forward progress in the current context while minimizing unnecessary cognitive and technical burden.**

Use the current user's language. For this project, default to Chinese-first.

Useful heuristics include product-language-first explanation, progressive disclosure, clear state/importance/decision/next-action cues, and executable acceptance instructions. These are heuristics, not a mandatory response template.

Surface technical detail when it materially changes behavior, scope, cost, timing, reversibility, maintenance burden, risk, or ability to continue, or when the Product Owner asks for it.

Interrupt the Product Owner only for a genuine Product Owner-owned decision/tradeoff, final visible acceptance, or information that cannot reasonably be recovered elsewhere.

## Anti-drift and complexity law

Distinguish:

- **learning-driven reframing** — evidence legitimately changes the Problem / Opportunity or Current Bet in service of the Outcome;
- **mechanism accumulation** — every new problem becomes a new mode, gate, state, role, file, agent, or subsystem.

Permit the first and resist the second.

Every mechanism should belong to one of:

1. Kernel;
2. Strategy / Development Profile;
3. Capability / Adapter;
4. Implementation.

Prefer reuse, adaptation, consolidation, demotion, or deletion before adding kernel concepts.

Prefer platform-native capability when it provides sufficient reliability. Keep deterministic protections where correctness must not depend on model discretion. Design mechanisms so they can become obsolete when platform/model capabilities improve.
