# Decision Readiness Routing

## Authority and purpose

This is the direct operational authority for PDC-4.5.3. It implements the already frozen Decision Readiness / Evidence Routing v3.1 as **internal Controller routing** inside the existing Explore, Preview, and Engineering modes.

The purpose is not to maximize information. It is to decide whether current evidence is sufficient for the next limited purpose and, only when it is not, choose the **lowest-cost credible route** that can resolve the material uncertainty.

## Runtime rule

### Default to action

**Default to action** for low-risk, low-cost, reversible work when no missing fact has a reasonable chance to materially change the decision. Do not insert a reflection, research, clarification, or approval ceremony merely because more information could exist.

Trigger evidence routing only when the missing fact could reasonably:

- **materially change** product direction, user-visible behavior, accepted scope, or the next investment decision;
- create **meaningful rework** if guessed incorrectly;
- undermine **evidence validity** or make the current conclusion misleading;
- affect a **significant investment**, high-cost action, or hard-to-reverse choice; or
- cross a qualified **specialist boundary**.

When none of those conditions applies, act. A clearly labeled temporary assumption is acceptable only for low-risk reversible detail under the rules below.

### Choose the lowest-cost credible route

Use the route that can credibly answer the actual missing question with the least unnecessary cost:

1. **Direct action** when evidence is already sufficient for the limited purpose or the remaining detail is low-risk and reversible.
2. **Internal context recovery** when the answer may already exist in project state, approved product facts/designs/decisions, historical evidence, or current code facts.
3. **Product Owner clarification** only for an unrecoverable, materially decision-changing question that belongs to Product Owner authority.
4. **External research** when mature standards, official workflows, open-source implementations, market products, or primary research are likely to exist and could change a consequential decision.
5. **Preview evidence** when the question can only be answered credibly through users, buyers, operations, real data, or a technical/product experiment.
6. **Specialist judgment** when correctness requires qualified security, safety, compliance, migration, deployment, or comparable expertise.

Routing is evidence-type driven, not a mandatory sequence. The one hard precedence rule is that a material rule that may already exist must go through internal recovery before Product Owner clarification.

## Internal context recovery before clarification

When a material rule is missing from the current conversation and may already exist, recover before asking the Product Owner:

1. current project state and current Change;
2. approved product facts, designs, decisions, and historical evidence;
3. current code and implementation facts when relevant.

If recovery succeeds, use the confirmed rule and continue. If recovery fails, state accurately that **no confirmed rule was found**. Do not infer or claim that the Product Owner never designed or decided it.

Block for Product Owner clarification only when **all three** are true:

- the answer **cannot be recovered** reliably from existing project material or evidence;
- different answers would materially change product behavior, experience, cost, priority, scope, or risk; and
- the choice **belongs to Product Owner authority**, rather than Controller judgment or a qualified specialist.

Ask the **smallest decisive concrete product question**. Provide consequences or a recommendation when that helps the Product Owner choose. Do not turn the Product Owner into a technical correctness oracle or a general requirements questionnaire.

## External research routing

Research proactively, without waiting for a Product Owner reminder, when mature prior art is likely and could materially change a consequential decision. Appropriate targets include official product/platform documentation, official repositories and source, standards/RFCs/regulatory material, primary research, and directly verifiable product behavior.

When **external research is already triggered** for an important, long-lived, high-cost, hard-to-reverse, or about-to-freeze decision, and a relevant primary source is reasonably available, a **primary/official source must be part of the core evidence before freeze**. Appropriate primary sources include the directly relevant official documentation, official repository or source code, standard/RFC/regulatory material, or original research. **Secondary sources may supplement** that evidence, but they **must not be the only freeze basis** in this case.

If an expected primary source cannot be accessed, **state the access limitation** and calibrate the conclusion accordingly; do not imply that it was inspected. Any statement that an official, primary, or otherwise authoritative source was checked **must match the actual evidence/source list** for that research run. Never claim evidence that is not actually present.

This is a source-quality rule after research has already been justified, not a new research trigger. Low-risk reversible details still default to action, and ordinary bounded research does not require mechanically collecting many sources.

Prefer **primary sources** when available. Research depth is proportional to:

- **decision impact**;
- current **uncertainty**; and
- expected **information value**: the chance new evidence will change the decision enough to justify the cost.

Use a light check for a reversible decision, targeted research for a bounded consequential choice, and deep research only for core strategy, core architecture, major commercial choices, high-cost/irreversible decisions, or comparable risk.

Research must end in a decision-oriented **reuse / adapt / innovate** judgment:

- **reuse** when an established mechanism fits the goal and constraints closely;
- **adapt** when the core mechanism is validated but the product, users, environment, or risks differ materially;
- **innovate** when existing approaches cannot satisfy a key constraint or differentiation is itself the product requirement.

External popularity, a paper, or a competitor design is evidence, not automatic Product Truth.

When this route is selected because the current optimization objective is meaningful **Explore**, continue with `references/outcome-directed-explore.md` for Outcome -> Problem / Opportunity -> Current Bet framing, independent evidence-family breadth, alternatives/counterevidence, Riskiest Assumption, exactly one decision-driving Primary Unknown, Decision Rule, Investment Appetite, and deliberate research stopping. Decision Readiness still decides whether more evidence is justified; Outcome-Directed Explore structures the Explore reasoning after that route is chosen.

## Stop research and route to Preview when reality must answer

Stop researching when current evidence is sufficient for the limited purpose and more sources are unlikely to change the next action. In particular, stop when a low-cost reversible action or experiment can generate better evidence than further reading.

Questions about actual adoption, willingness to pay, repeated behavior, operational use, real-data performance, or other reality-only outcomes must route to the existing Preview evidence path. Choose the **lowest-cost credible Preview** that can answer the Primary Unknown; do not substitute more desk research for missing real-world evidence.

This routing rule selects the existing Preview path. When the missing reality evidence requires **runnable code** and that runnable artifact is the **cheapest credible evidence**, route to the **Fast Preview** execution profile in `references/product-experiment-workflow.md`. Fast Preview is **still Preview**; Decision Readiness does not own its execution mechanics, create prototype automation, or add a new Preview lifecycle.

## Specialist judgment

Qualified correctness remains specialist-owned. Route to an appropriate specialist for **security**, **authorization**, tenant isolation, **sensitive data**, irreversible **migration**, **deployment safety**, **compliance**, and comparable qualified boundaries.

The Controller should translate the remaining product impact, cost, or option tradeoff for the Product Owner when needed, but must not ask the Product Owner to guess specialist correctness.

## Temporary assumptions

A temporary assumption is bounded direct action, not a new evidence class or approval state. It may cover only **low-risk reversible detail**, must be recognizable as provisional, and must be easy to replace.

If the same assumption later affects **user-visible completion or acceptance** in Engineering, it must be resolved from evidence or explicitly encoded as approved product behavior **before freeze**. A temporary label cannot silently become part of the frozen completion boundary.

## Frozen Engineering boundary

Decision readiness primarily improves decisions before they are frozen. After an Engineering contract is frozen, new research, competitor findings, or newly discovered best practices **cannot move the finish line**.

They become a suggestion, backlog item, or future Change unless either:

- an already **authorized intent change** changes the completion boundary through the normal contract-revision path; or
- a permitted **universal stop condition** is causally triggered by the current change.

Do not add new acceptance criteria merely because a better design is discovered after freeze.

## Independent Controller judgment

A Product Owner proposal is a **candidate solution**, not an automatic fact. The Controller must distinguish goal/problem from proposed solution, challenge material weakness, and present a materially better alternative when evidence supports one.

Do not manufacture disagreement. When the proposal is reasonable, support it. After an **informed ordinary-risk choice**, do not relitigate it absent **new material evidence**, a material conflict with approved behavior, or a specialist boundary.

Product Owner decision authority, Controller recommendation authority, and specialist-only correctness boundaries remain unchanged.

## Complexity boundary

Decision readiness is internal routing, not a new workflow layer. PDC-4.5.3 introduces:

- **no fourth mode**;
- **no new lifecycle state**;
- **no routine Product Owner gate**;
- **no mandatory readiness artifact** or user-facing checklist;
- **no automatic research daemon** or hidden research agent;
- no numeric readiness score;
- no permanent External Researcher decision role;
- no Fast Preview engine, Multi-Change runtime, Promotion Gate, or later-roadmap mechanics. PDC-4.5.4 adds bounded Outcome-Directed Explore behavior through `references/outcome-directed-explore.md`, not a new workflow engine or state machine.

After the route is chosen, execute or present **one required next action** owned by the real responsible role. Do not expose internal readiness analysis unless it changes a product decision or requires Product Owner action.
