# Review and Assurance Routing

## Purpose

Choose review independence based on the assurance claim and review object. Do not create fresh-session ceremony where it buys no distinct assurance, and do not weaken fresh-context requirements where absence of prior priming is part of the claim.

## Architecture / operating-model review

For a material operating-model, authority, evidence, concurrency, specialist-boundary, or assurance-system change, use an independent architecture reviewer who did not draft the candidate.

A separate context can reduce shared framing, but a **literal fresh session is not required** merely to establish architecture independence.

After an `ADJUST`, when corrections remain bounded to identified blockers plus necessary regressions, route the **same independent reviewer** to **bounded re-review**. Require a new full review only when the correction materially changes direction, adds a new core mechanism, expands normative scope, or compromises reviewer independence.

## Fresh-context model-behavior assurance

Use **Fresh-context model-behavior assurance** when the claim depends on **absence of conversational priming**. A same-context Controller self-check is regression evidence, not independent fresh-context evidence. Architecture approval cannot substitute for this assurance class.

## Engineering implementation review

For **Engineering implementation review**, the **coding agent may not approve its own implementation**. Preserve the frozen contract, exact review target, Controller-run required tests, bounded review, product acceptance, and integration verification.

A **new chat/session is not required** merely to create Engineering reviewer independence; independence comes from role separation and evidence against the exact review target.

## Qualified specialist review

Use **Qualified specialist review** for security, authorization, tenant isolation, sensitive data, migrations, deployment safety, compliance, or other specialist-only boundaries. Here **reviewer qualification matters more than conversational freshness**.

## Routing rule

Use only the assurance that the claim actually needs. Review ceremony without a distinct assurance benefit is not a substitute for evidence.

## Bounded evidence reuse routing

During a contract-authorized bounded behavior re-review, route each prior PASS scenario to reuse only when its predeclared evidence-unit inputs are unchanged and the Controller can still defend the same evaluator, causal, and assurance claim. Preserve the prior run/commit/transcript provenance and assurance class.

Route failed, missing, new, changed, causally affected, materially context-changed, or uncertain scenarios to fresh final-target execution. If the impact map was absent before the first run, was narrowed after a failure, is ambiguous, or omits a plausible cross-cutting dependency, fail closed to broader or full fresh execution. A targeted fresh run remains partial evidence; only the Controller may compose it with eligible prior evidence when the frozen contract explicitly permits composition.
