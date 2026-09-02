# Development Profile Routing

## Purpose

Use this reference when PDC needs object-specific development or verification behavior after the universal control decision is clear.

A **Development Profile** is the single extensibility seam between the stable PDC kernel and the mechanics of a particular deliverable/runtime.

Profiles adapt methods. They do not create new PDC cores or new operating modes.

## What a Profile may define

A Profile may define the minimum object-specific details needed to control work credibly:

- authoritative source/artifact/runtime identity;
- available Builders, tools, specialist Skills, platforms, or human implementation capabilities;
- object-specific specification concerns;
- Preview methods and credible-fidelity dimensions;
- Engineering verification dimensions;
- specialist boundaries;
- delivery/integration semantics;
- rollback/recovery semantics;
- freshness/versioning/checkpoint mechanisms;
- platform-native capabilities that should be reused instead of rebuilt.

## What a Profile may not redefine

A Profile may not redefine:

- Product Owner authority;
- Controller independent judgment;
- the Builder's inability to self-approve;
- the exactly three Modes: Explore / Preview / Engineering;
- the one advancing Work Focus rule;
- the Engineering completion law;
- the distinction between technical PASS and Product Owner visible acceptance;
- the no-moving-goalposts rule;
- specialist-only correctness boundaries.

## Deliverable form is not required input

Do not force the Product Owner to choose a Profile before the correct deliverable form is sufficiently understood.

During Explore, Skill / Agent / automation / software / manual process / reuse / hybrid are candidate forms.

Select or narrow a Profile when the current evidence/decision requires object-specific methods.

## Profile selection rule

Choose the smallest Profile/capability combination that can credibly execute the current next action.

Prefer in this order when fit is sufficient:

1. existing platform-native capability;
2. installed specialist Skill/tool/connector;
3. established current PDC Profile;
4. a bounded adapter around an existing capability;
5. new profile behavior only when a demonstrated gap prevents the Outcome.

Do not build a generic framework before a real deliverable demonstrates the need.

## PDC control vs specialist expertise

PDC remains the control plane even when a specialist Skill or tool performs the development work.

PDC owns:

- Outcome and current Work control;
- Mode and one required next action;
- product scope/intent protection;
- evidence sufficiency for the current claim;
- Engineering completion boundary when Engineering applies;
- acceptance/delivery/closure control.

The specialist capability owns its domain method.

Examples:

- Skill development may delegate Skill structure/validation/package mechanics to `skill-creator` while PDC controls the product Outcome, Work boundary, evidence, and acceptance.
- Software implementation may delegate code changes to a Coding Agent while the Software/PDC Profile preserves frozen contract and exact-target Controller verification.
- A platform-native automation builder may own trigger/action configuration while PDC controls the approved behavior, evidence, and delivery decision.

Do not copy a specialist Skill's entire method into PDC merely so PDC can appear self-contained.

## Current implemented profile boundary

At the current candidate baseline, the only fully implemented strict formal Engineering Profile is:

- **Software/PDC** — repository-backed Engineering using the existing PDC Git/contract/snapshot/test/review/acceptance/integration machinery.

Load `references/profile-software-pdc.md` for that path.

Architecture v2 product scope is broader than this current implementation coverage.

Do **not** claim that formal Skill, Agent, automation/workflow, or external-platform Engineering Profiles already exist merely because PDC can Explore or Preview those deliverables or invoke a specialist capability.

## Unsupported formal Engineering profile

When a non-Software/PDC deliverable reaches a point where the user requests a strict Engineering completion claim but no credible Profile exists:

1. do not pretend the Software/PDC Git mechanism automatically applies;
2. do not let the Builder become sole correctness authority;
3. identify the minimum missing evidence/authority mechanism for that deliverable;
4. reuse platform-native/specialist capability where sufficient;
5. if the gap is material, open a separately bounded profile/adapter development change or keep the claim at a narrower supported level;
6. state the current assurance boundary plainly to the Product Owner.

Fail closed on the unsupported claim, not on all useful work.

Explore and Preview may continue when their evidence requirements are credible without a formal Engineering Profile.

## Initial profile evolution strategy

Do not implement all profiles at once.

The first proven non-software target should be a real deliverable with real evidence. Architecture v2 currently recommends **Skill** as a useful first validation target because PDC itself is a Skill and specialist Skill creation/validation capability already exists.

Treat future Agent and automation/workflow Profiles as separate evidence-driven additions.

## Anti-duplication rule

Before adding profile machinery, classify the need as:

- **Reuse** — current platform/profile/specialist capability already satisfies it;
- **Adapt** — existing capability is sufficient with a thin adapter;
- **Innovate** — a real gap remains after reuse/adaptation.

A new mode, parallel PDC core, duplicate workflow engine, duplicate evaluator, permanent multi-agent topology, scheduler, or dependency system is not a Profile.
