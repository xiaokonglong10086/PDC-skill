# Assurance Routing

## Purpose

Derive the assurance requirements for the current **formal Engineering** Work/claim. Assurance routing is a **Control Decision derivative**: per Control Decision, it computes which additive assurance requirements apply on top of the Universal Assurance Floor. It is deliberately not a Mode, not a lifecycle state, not a workflow engine, not an approval ladder, not a universal stage router, and not a generic risk-management subsystem; it is also not a Development Profile, a persisted Product Truth, or a separate truth authority.

Keep the PDC kernel at exactly five concepts and three Modes. The Modes remain exactly Explore / Preview / Engineering.

## Scope precondition

Assurance routing applies **only after the current Control Decision has already selected formal Engineering for the Work/claim**. It tailors additional assurance for that Work/claim; it never decides whether to enter Engineering, and it never routes the Work itself.

For a Work not yet confirmed for Engineering, assurance routing does not force Engineering, does not require research, does not require Preview, and does not require Product Owner clarification. Those decisions remain entirely with the existing Mode classification, Decision Readiness Routing, and Explore/Preview routing.

## Responsibility separation

Three routing concerns stay separate; GF-M2 reuses the existing authorities rather than re-implementing them:

- **Decision Readiness Routing** (`references/decision-readiness-routing.md`): answers which evidence/action route the current decision needs now (direct action, internal context recovery, Product Owner clarification, external research, Preview evidence, specialist judgment). GF-M2 does not duplicate these rules.
- **Assurance Routing (this reference)**: only after formal Engineering is already selected, answers what additional assurance the Engineering Work/claim needs on top of the non-weakenable floor (from Consequence / Reversibility / Specialist Boundary).
- **Review Assurance Routing** (`references/review-assurance-routing.md`): when verification is already required, answers what reviewer independence or qualification the claim/object needs. GF-M2 does not duplicate the reviewer taxonomy.

## Universal Assurance Floor (non-weakenable)

For any formal Engineering claim, all ten floor items hold regardless of routed assurance:

1. the completion boundary is explicit and cannot silently move after freeze;
2. the Builder cannot redefine Intent;
3. the Builder cannot self-approve;
4. verification is independent enough for the claim;
5. verification binds the actual deliverable / version / runtime under review;
6. technical PASS is distinct from Product Owner acceptance;
7. causally applicable specialist/safety correctness can stop work;
8. unrelated debt / optional improvements cannot move the finish line;
9. accepted work advances to delivery/integration or an explicit blocker;
10. closure and evidence remain recoverable.

Low risk may reduce assurance *cost* but never removes a floor item. The floor is already expressed by the Engineering completion law in `references/architecture-v2-kernel.md`; reuse that authority.

## Routing inputs

The Controller derives assurance requirements from exactly three core inputs:

- **Consequence** — what failure costs: local/easy-to-discover → user-visible behavior error → data/permission/business-critical → security/privacy/compliance/production incident.
- **Reversibility** — how hard recovery is: immediate/low-cost/stateless → rollback-able → data/state impact → irreversible/high-cost.
- **Specialist Boundary** — whether qualified correctness is required: security / authorization / tenant isolation / sensitive data / migrations / deployment safety / compliance / other specialist-only correctness.

Additional routing signals may be added only when proven to change an assurance decision; no dimension is invented for completeness.

## Additive assurance outputs

Baseline + additive tailoring: assurance routing adds requirements on top of the floor; it **never removes independent verification or evidence**. Additive dimensions:

- verification depth;
- verification method;
- number/type of independent checks;
- specialist involvement;
- behavior-evaluation depth;
- isolation/environment requirements;
- rollback/checkpoint assurance;
- delivery verification;
- production/runtime evidence.

These are derived assurance requirements for the current formal Engineering Work — never a new persisted top-level product concept.

## Specialist boundary

When a specialist boundary is touched, ordinary Controller/Builder assurance **does not substitute specialist judgment**; route to a qualified specialist. If a specialist boundary is touched and **no specialist is available**, fail closed (record the blocker / executable handoff via the existing capability-and-assurance semantics). The Product Owner is never asked to substitute specialist correctness.

## False escalation and false de-escalation

- **No false escalation**: high code volume or technical jargon alone does not raise assurance to maximum.
- **No false de-escalation**: a small diff that touches consequence or specialist risk does not lower assurance.

## Product Owner disclosure

The PO sees, in product language: why more or less verification is needed; the practical time/cost/risk impact; whether a genuine PO-owned tradeoff exists; and the one next action. The PO is not shown an assurance score, risk matrix, internal level, technical checklist, or raw test taxonomy by default. Ordinary assurance routing is Controller technical judgment; only a genuine product tradeoff escalates to the PO.

## Representative scenarios

| ID | Scenario | Routed assurance | Truth standard |
|---|---|---|---|
| AR-01 | Low-risk reversible (small copy/display) | cheap assurance; floor intact | unchanged |
| AR-02 | Ordinary Engineering | standard Software/PDC verification depth; no unrelated specialist ceremony | unchanged |
| AR-03 | High-consequence / difficult rollback | additive depth + isolation / rollback / checkpoint / delivery verification | unchanged |
| AR-04 | Specialist-risk (authorization/tenant/sensitive data) | route to qualified specialist; PO never substitutes specialist | unchanged |
| AR-05 | False escalation (multiple files / many technical nouns, actually low-risk reversible) | low assurance despite surface complexity | unchanged |
| AR-06 | False de-escalation (small diff touching authority/data/production safety) | high assurance despite small diff | unchanged |

## Anti-drift boundary

Assurance routing must never become: an entry gate into Engineering; a second Decision Readiness; a second Mode router; a risk score engine; a Low / Medium / High assurance class system; a mandatory approval ladder; a second lifecycle; a second workflow engine. It never judges whether to enter Engineering, whether research is needed, whether Preview is needed, whether Product Owner clarification is needed, or whether current evidence suffices for a product-direction decision.

## Result and data destination

The routing decision and its rationale are recorded as part of the normal Control Decision / Work-control authority record. No new durable truth system is created; assurance routing is a projection, not persisted Product Truth.