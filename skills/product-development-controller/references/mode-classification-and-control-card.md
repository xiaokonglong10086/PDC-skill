# Mode Classification and Product Owner Control Card

## Purpose

Use this reference when the product owner asks what is happening, which mode fits, or what must happen next.

PDC-4.4 adds a **classification and presentation layer only**. It does not create a new lifecycle state machine and it does not mutate `workflow-state.json` merely because a mode was classified.

The classification question is: **what is the current optimization objective?** Code presence, prototype polish, repository state, or implementation technology does not determine the mode.

## Classify exactly one current mode

### Explore

Choose **Explore** when the fastest useful progress is reducing product-direction uncertainty before a meaningful real-user experiment or sufficiently understood Engineering task exists.

Product-language reason pattern: “The main uncertainty is still what product behavior is worth pursuing, so the next step should reduce that uncertainty rather than optimize implementation.”

For Explore, identify one **Primary Unknown** when it is relevant to the current focus.

### Preview

Choose **Preview** when the fastest useful progress is obtaining real product/user evidence about a clear Primary Unknown with the smallest credible closed loop.

Product-language reason pattern: “We know what we need to learn and have enough of the experience to test it, so the next step is evidence from real use rather than production hardening.”

A Preview may be fit for the current experiment while still being unfit for production delivery. State both judgments explicitly when that distinction matters.

### Engineering

Choose **Engineering** when the intended product behavior is sufficiently understood or already approved and the current objective is reliable implementation, repair, maintenance, or engineering quality.

Product-language reason pattern: “The desired behavior is already clear; the remaining work is to implement or restore it reliably.”

Known approved behavior may route directly to Engineering without forcing Explore or Preview. State the approved/understood basis when it materially helps the product owner understand the classification.

### Classification rules

- Classify **exactly one** current mode: Explore, Preview, or Engineering.
- Classify by the **current optimization objective**, not by whether code exists.
- Do not add a fourth operating mode.
- A classification is a Controller judgment and presentation result. It is not a formal workflow transition.
- Do not mutate Engineering workflow state solely because the classification changed.
- PDC-4.4 does not execute Explore/Preview workflows, Preview -> Engineering promotion, or Direct Engineering transitions.
- If evidence is insufficient to classify responsibly, the one next action is to obtain the missing evidence; do not fabricate certainty.

## Product Owner Control Card

The default product-owner view puts product meaning first. It must be understandable without Git, code, test-framework, architecture, protocol, database, or security expertise.

Present these fields in this order unless a compact answer can combine adjacent fields without losing meaning:

1. **Current mode** — Explore, Preview, or Engineering.
2. **Current purpose** — the outcome this step is trying to achieve.
3. **Why this mode fits** — one product-language reason tied to the optimization objective.
4. **Already verified** — only facts that materially support the current judgment.
5. **Still insufficient** — the exact missing evidence, behavior, reliability, or decision; say “none for the current purpose” when none remains.
6. **Fitness for Current Purpose** — whether the current result is sufficient for the present objective, without implying production fitness when that has not been established.
7. **One required next action** — one executable action, not a menu of optional work.
8. **Responsible role** — Controller, Coding Agent, Product Owner, Technical/Security Specialist, or External Reviewer.
9. **Advancement condition** — the observable evidence or decision that allows the work to advance.

Conditional fields:

- **Primary Unknown** — show for Explore/Preview when relevant.
- **Engineering basis** — show for Engineering when the approved or sufficiently understood behavior explains why discovery is unnecessary.
- **Product owner decision** — show only when the product owner actually has a product tradeoff, scope, priority, investment, or acceptance decision to make.
- **Technical impact / specialist handoff** — show only when technical facts change a product decision or require specialist judgment.

Do not fill the card with empty labels. Omit conditional fields that are not applicable.

## Progressive technical disclosure

Technical evidence must remain available to Controller, Coding Agent, Reviewer, and specialists, but it is not the default product-owner interface.

Hide by default when it does not change a product decision, current risk, cost, timing, or ability to continue:

- Git SHA, branch, worktree, commit and diff mechanics;
- contract digests, schema versions, record digests, evidence hashes;
- raw test logs, stack traces, test-framework configuration;
- framework, protocol, API, database, deployment, or low-level architecture choices;
- specialist implementation details the product owner cannot reasonably verify.

If the product owner explicitly asks for technical evidence, provide it separately without replacing the product-language Control Card.

## Route technical questions by decision ownership

### 1. Controller-owned technical detail

When the issue can be resolved from repository evidence, tests, tools, or established engineering rules and the product owner has no product decision to make:

- handle it inside Controller/Coding Agent/Reviewer work;
- keep low-level detail out of the default card;
- tell the product owner only whether it changes the current purpose, risk, timing, or next action.

Do not ask the product owner to judge Git correctness, test completeness, code quality, framework configuration, schema validity, or similar implementation evidence.

### 2. Product tradeoff

When a technical choice changes a product dimension the owner can reasonably decide, translate the question before asking it.

Translate into concrete effects such as:

- user experience or latency;
- scope or capability;
- delivery time;
- cost or ongoing maintenance burden;
- operational or product risk;
- reversibility.

Ask the product question, not the technology question.

Example: do not ask “WebSocket or SSE?” Ask whether near-real-time user feedback is worth higher implementation/maintenance cost versus a few seconds of delay with a simpler, more stable implementation.

### 3. Specialist-only judgment

When correctness requires professional technical or safety expertise the product owner cannot reasonably supply, such as production authentication, authorization, tenant isolation, sensitive-data handling, irreversible migrations, deployment security, or disaster recovery:

- state that a Technical/Security Specialist is required;
- explain the product impact in plain language;
- give one concrete handoff action;
- say whether the current objective can continue while the judgment is pending or exactly what is blocked;
- do not ask the product owner to guess the technically correct solution.

A concrete handoff names the question and required judgment, for example: “Send the tenant-isolation design and these three questions to the technical/security lead for approval before production delivery.”

The PDC-4.4 classification layer remains presentation-only. When the current mode is Preview, PDC-4.5 adds the full Resource Escalation workflow through `product-experiment-workflow.md`; this does not change the classification rules above or create a new operating mode.

## Product-owner acceptance and action instructions

When the product owner must act or accept, make the instruction executable:

1. **Do:** state the exact action to perform.
2. **Observe:** state what user-visible result or decision evidence to look at.
3. **Pass:** state what observable result counts as passing.
4. **Fail:** state what mismatch counts as failing.
5. **If it fails:** the product owner only needs to identify where reality differs from the expected product result; they do not need to propose a technical fix.

Never ask the product owner to inspect code, Git, hashes, schemas, raw test logs, frameworks, protocols, databases, or professional security correctness as an acceptance condition.

## Representative cards

### Explore — ambiguous product direction

- **Current mode:** Explore
- **Current purpose:** identify the first product behavior worth validating for the game-based training platform idea.
- **Why this mode fits:** the largest risk is still product direction, not implementation reliability.
- **Primary Unknown:** which employee behavior/problem must the first experience prove it can improve?
- **Already verified:** the broad business goal is known.
- **Still insufficient:** no single product assumption has yet been selected as the decisive test.
- **Fitness for Current Purpose:** not yet fit for a meaningful user experiment.
- **One required next action:** Controller narrows the idea to one Primary Unknown and one observable user outcome.
- **Responsible role:** Controller
- **Advancement condition:** one falsifiable Primary Unknown and a smallest credible test are defined.

### Preview — usable experiment, not production delivery

- **Current mode:** Preview
- **Current purpose:** learn whether employees can complete and understand the imported three-question training loop.
- **Why this mode fits:** the loop already exists; real user evidence is now more valuable than production hardening.
- **Primary Unknown:** can target employees complete the loop and understand the feedback without assistance?
- **Already verified:** import, answering, and correctness feedback work for the experiment.
- **Still insufficient:** no real-user behavior evidence and no production-readiness evidence.
- **Fitness for Current Purpose:** fit for the current user experiment; not established as fit for formal customer delivery.
- **One required next action:** run the smallest representative employee trial and capture observed completion/understanding evidence.
- **Responsible role:** Product Owner / Controller
- **Advancement condition:** the trial produces enough evidence to decide whether to continue Preview, return to Explore, stop, or later request Engineering evaluation.

### Engineering — approved behavior regression

- **Current mode:** Engineering
- **Current purpose:** restore the approved result display after submit.
- **Why this mode fits:** the intended user behavior is already approved; the remaining problem is reliable repair.
- **Engineering basis:** the result-display behavior is known and previously accepted.
- **Already verified:** submitting currently fails to show the result.
- **Still insufficient:** the repair has not yet passed the frozen Engineering checks and product acceptance.
- **Fitness for Current Purpose:** not fit until the approved result behavior is restored and verified.
- **One required next action:** Coding Agent implements the bounded repair under the frozen contract.
- **Responsible role:** Coding Agent
- **Advancement condition:** the exact repair passes contracted review evidence and the product owner observes the approved result behavior.

## PDC-4.4 boundaries

PDC-4.4 does not implement:

- Product Experiment / Preview workflow;
- Learning Ledger;
- Preview -> Engineering Promotion Gate;
- formal Direct Engineering state transitions;
- Product Truth or Engineering Facts persistence/writeback;
- Constitution;
- release observation;
- queued/waiting multi-change control;
- automatic or hidden multi-agent orchestration;
- a fourth operating mode.

Record useful ideas in these areas as future work. They cannot become hidden completion criteria for the current PDC-4.4 task.

## PDC-4.5 Preview execution overlay

PDC-4.5 now implements **Product Experiment / Preview workflow**, **Learning Ledger**, and the **full Resource Escalation workflow** in the separate `product-experiment-workflow.md` reference while preserving every PDC-4.4 classification and readability rule in this file.

When the mode is Preview, keep this Control Card as the product-owner interface and populate it from the recovered experiment evidence:

- keep exactly one Primary Unknown visible;
- distinguish observed evidence from owner interpretation;
- state Fitness for Current Purpose separately from production fitness;
- make the one next experiment action executable;
- use full Resource Escalation only when a blocker actually needs escalation;
- record non-causal future Engineering concerns without stopping the current Preview.

PDC-4.5 still does not implement **Preview -> Engineering Promotion Gate**, **formal Direct Engineering state transitions**, production qualification of Preview code, Product Truth or Engineering Facts persistence/writeback, Constitution, or automatic or hidden multi-agent orchestration. A successful Preview may end as `Engineering Candidate` only.
