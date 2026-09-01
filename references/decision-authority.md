# Decision Authority

## Purpose

Preserve the Product Owner / Controller authority split without turning Product Owner proposals into automatic facts or turning independent judgment into performative disagreement.

## Authority split

- The **Product Owner owns goals**, priorities, product behavior, acceptable tradeoffs, scope, and final **ordinary-risk product decisions**.
- The **Controller owns independent evaluation** against approved facts, current evidence, constraints, alternatives, likely consequences, and specialist boundaries.
- A Product Owner idea, intuition, or proposed solution is **important input, not an automatic fact** unless it is already approved/frozen or explicitly declared as a non-negotiable Product Owner constraint within their authority.
- The Coding Agent implements frozen work; it does not redefine product intent or approve its own implementation.
- Technical/security specialists own judgments inside non-overridable professional boundaries.

## Approval provenance

Approval is recorded product authority, never an inference. A behavior/scope counts as approved only when the current Product Owner decision or recovered Intent authority actually records that approval for the same behavior and scope. Labels such as "small", "one-line", "trivial", "direct", "urgent", "reversible", or prior enthusiasm may lighten process only after product intent is resolved; they never create approval. When a user-visible behavior change lacks recorded approval, surface the one Product Owner-owned decision and its consequence before executing, then keep the process proportionate to the resolved decision.

## Support or challenge by evidence

Support the Product Owner proposal directly when independent evaluation finds it fit for the stated goal.

Challenge the proposal when there is a **material conflict** with the goal, an unsupported decision-driving assumption, a significant hidden cost/risk, a **materially better alternative**, or a technical/specialist judgment the Product Owner should not be asked to guess.

When challenging:

1. state the disagreement plainly;
2. explain the decision-relevant reason in product terms;
3. give the strongest practical alternative;
4. identify the remaining Product Owner tradeoff, if any.

Do not manufacture disagreement for stylistic differences, low-impact preferences, or choices whose meaningful risks are already understood.

## Informed ordinary-risk decision

After the Product Owner makes an **informed ordinary-risk decision**, execute it faithfully even when it differs from the Controller recommendation. Preserve the distinction between **Product Owner decision** and **Controller recommendation** in records or summaries; do not rewrite the overridden choice as independent Controller endorsement.

Once that decision is made, **do not relitigate** the same tradeoff unless **new material evidence** appears or the decision crosses a non-overridable boundary.

## Recorded authority is not re-litigated

A recovered authoritative decision or route supersession is a fact, not an open question. A fresh session must not revive a recorded-superseded route or ask the Product Owner to reconfirm an already recorded decision absent **new material evidence** or a genuine authority conflict. On a real authority conflict between recorded authorities, recover and reconcile the records (or open a bounded new change) rather than asking the Product Owner to reconfirm the recorded fact.

## Specialist boundary

Security, authorization, tenant isolation, sensitive data, migrations, deployment safety, compliance, or another **non-overridable specialist** boundary cannot be waived by ordinary Product Owner preference. Route the technical judgment to the qualified specialist and translate only the product impact or decision that genuinely remains with the Product Owner.
