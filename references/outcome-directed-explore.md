# Outcome-Directed Explore

## Authority and purpose

Use this reference only when the current operating mode is genuinely **Explore**: the current optimization objective is to reduce material product-direction uncertainty. It is the detailed one-level authority for the Outcome-Directed Explore behavior added by PDC-4.5.4.

It does not create a fourth mode, lifecycle state, mandatory Explore artifact, approval gate, permanent research role, or background research service. Low-risk reversible work that is already decision-ready still follows Decision Readiness and defaults to direct action.

## Start from Outcome, not the requested feature

For meaningful Explore, recover the desired **Outcome** from project context before treating the latest proposed feature as the work definition. The compact trace is:

**Outcome -> Problem / Opportunity -> Current Bet -> Riskiest Assumption -> exactly one decision-driving Primary Unknown**

Keep these concepts separate:

- **Outcome** — the user, buyer, operator, business, or product-system result worth achieving.
- **Problem / Opportunity** — the condition preventing or enabling that outcome, stated independently of a proposed implementation.
- **Current Bet** — the present candidate solution or direction. The Product Owner's proposed solution is important input, but it is **not automatic Product Truth**.

If the Outcome can be recovered from approved project facts, roadmap, decisions, prior learning, or other trustworthy project state, use it and continue. Ask the Product Owner only when no reliable outcome can be recovered and different outcomes would materially change the decision. Ask the smallest decisive product question rather than a questionnaire.

A metric is useful when it is already meaningful, but Explore does not invent false precision just to make the Outcome numeric.

## External Evidence Sweep

When Explore concerns a meaningful product-direction decision and relevant external knowledge is reasonably available, proactively research before convergence. This is the normal path for material Explore, not a Product Owner reminder-driven option.

Research breadth is defined by relevant **independent evidence families**, not by a fixed number of links; there is **no fixed source count**. Depending on the decision, useful families can include:

- competitors, substitutes, adjacent products, and directly observable market behavior;
- official product/platform documentation, standards, RFCs, regulatory or authority material;
- official repositories, open-source implementations, issues/discussions, and implementation precedents;
- original/primary research and credible industry evidence;
- public user, buyer, or operator evidence when it provides useful prior information.

For core strategy, core PDC mechanisms, major architecture, business-model choices, or other high-cost/hard-to-reverse directions, research should normally span several independent evidence families when reasonably available. For narrower Explore, use the smallest multi-source-family sweep that has a credible chance of changing the decision.

For core claims, prefer relevant **primary/official** evidence when reasonably available. Secondary sources may help discovery or context but should not replace available primary evidence for a consequential freeze basis. Any claim that an official, primary, or authoritative source was checked must match the **actual evidence/source list**. If the expected source cannot be accessed, state the limitation rather than implying it was inspected.

Research is evidence, not authority. Competitor popularity, a framework, a paper, or a common pattern never becomes Product Truth merely because it exists.

## Compare alternatives, counterevidence, and failure modes

When solution uncertainty is material, do not research only to confirm the Current Bet. Look for the strongest credible decision-relevant challenge, which may be:

- a materially different alternative;
- a known failure mode or constraint;
- counterevidence against the bet;
- a no-build, manual, or simpler path when relevant.

Do not manufacture opposition. If comparison shows the Current Bet remains the strongest practical option for the Outcome and constraints, support it and state what evidence increased confidence.

End the external synthesis with one of these judgments:

- **Reuse** — an existing mechanism fits the Outcome and constraints closely.
- **Adapt** — a validated mechanism is useful but product, user, business, environment, or risk differences require changes.
- **Innovate** — prior art cannot satisfy a critical constraint or differentiation is itself necessary to the product result.

The judgment is about fit to the current decision, not prestige of the source.

## Identify the Riskiest Assumption

Use **value**, **usability**, **feasibility**, **viability**, specialist/ethical constraints, and other domain-specific risk families as **optional lenses**, not a mandatory four-part checklist.

Select the **Riskiest Assumption** by combining:

1. decision impact — how strongly failure would change or kill the Current Bet;
2. current uncertainty — how weakly the assumption is supported today; and
3. reducibility — whether further evidence can credibly reduce that uncertainty within the Investment Appetite.

Do not manufacture four tests merely because four familiar risk labels exist.

## Form exactly one decision-driving Primary Unknown

Convert the current Riskiest Assumption into **exactly one decision-driving Primary Unknown**: a question whose answer can change the current product direction, investment decision, or evidence route.

Keep **Supporting Assumptions** subordinate when several assumptions jointly determine the same decision. They can be tested as parts of the same learning question without becoming competing current Primary Unknowns.

If another unknown can independently change investment or direction, do not hide it as a Supporting Assumption. Record it as a **separate/sequential Primary Unknown** to be handled after or instead of the current one.

Exactly one Primary Unknown is current; this does not pretend that only one uncertainty exists in the product.

## Pre-state the Decision Rule

Before collecting decisive evidence, state an observable **Decision Rule** for interpreting it. Define what evidence would:

- **support** the Current Bet enough for the next limited purpose;
- **weaken** or reframe the bet; or
- **reject** or stop the bet.

Use a qualitative rule when a numeric threshold would be false precision. The rule must still be observable enough to prevent post-hoc rationalization after the result is known.

## Set a proportionate Investment Appetite

State the **Investment Appetite** for learning: how much time, cost, complexity, or evidence effort is justified before the work should be reframed or stopped.

The Controller may choose a bounded default when the tradeoff is low-risk and reversible. Ask the Product Owner only when the appetite itself is a material priority, spend, timing, or strategic tradeoff owned by the Product Owner.

Investment Appetite is proportional decision discipline, not a fixed six-week cycle, mandatory timebox, readiness score, or approval gate.

## Choose the cheapest credible next route

Once the Explore frame is decision-ready, choose one next action according to the evidence type required:

- **Continue Explore** when additional internal or external evidence still has a meaningful probability of changing the Problem / Opportunity, Current Bet, or Primary Unknown.
- **Preview** when the Primary Unknown requires users, buyers, operators, real data, actual behavior, a technical/product experiment, or other reality evidence.
- **Specialist judgment** when qualified correctness is the unresolved boundary, including security, authorization, privacy, compliance, irreversible migration, deployment safety, or comparable specialist-owned risk.
- **Stop** when evidence shows the opportunity or Current Bet is not worth further investment.
- **Reclassify to Engineering** only under the existing three-mode classification rules when product behavior is sufficiently understood/approved and no material product-direction unknown remains.

This is route selection only. When the chosen Preview evidence requires runnable code and it is the cheapest credible evidence, the route may use the **Fast Preview** **Preview execution profile** defined in `references/product-experiment-workflow.md`; Explore **does not own Fast Preview execution mechanics**. It does not implement formal Promotion or Direct Engineering lifecycle transitions, Multi-Change, or later roadmap mechanics.

## Stop research deliberately

Research is complete for the current limited decision when its **marginal information value** is low. Stop desk research when any of these is true:

- current evidence is sufficient for the current limited decision;
- additional sources are mostly repeating known patterns and are unlikely to change the next action;
- a low-cost real-world test can produce stronger information than more reading;
- the Investment Appetite has been reached and further desk research is not justified by expected decision value.

Do not continue merely because more sources exist.

Reality-only questions cannot be researched away. Actual adoption, repeated behavior, willingness to pay, operational use, real-data performance, or comparable real-world outcomes route to **Preview**. Specialist-only correctness routes to **Specialist judgment**. External evidence can establish priors, not substitute for the evidence type the decision actually requires.

## Product Owner interface

Keep the owner-facing result **compact** and decision-relevant. For a consequential Explore judgment, normally present only:

- desired Outcome;
- actual Problem / Opportunity;
- the external evidence synthesis that materially changed or confirmed the decision;
- Current Bet and strongest practical alternative when material;
- Riskiest Assumption and current Primary Unknown;
- Decision Rule or Investment Appetite only when it changes the decision;
- one required next action and responsible role.

Raw source matrices, risk grids, technical notes, exhaustive research logs, and internal reasoning are Controller-side evidence unless they change a Product Owner decision or the Product Owner asks for them. Do not create a mandatory new Explore document or user-facing form.

## Low-impact boundary

Outcome-Directed Explore is not a research ceremony. **Low-risk reversible** work — that is, low-risk reversible work that is already sufficiently understood remains on the PDC-4.5.3 default-to-action path. Do not force Explore or external research simply because research capability exists.

After an Engineering contract is frozen, new Explore findings cannot move that frozen finish line except through the already-authorized contract-revision path or a permitted current-change-scoped universal stop condition.
