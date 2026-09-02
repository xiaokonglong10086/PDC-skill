# Handoff Interface

## Human Courier boundary

**Human Courier** is a **transfer action**, not a decision role. It exists only when direct agent-to-agent or tool-mediated transfer is unavailable and a person must physically carry a technical package between roles or environments.

If **direct delegation** or direct tool transfer is available, use it and do not ask the Product Owner to relay technical material manually.

If a manual transfer is genuinely required, give the Product Owner **one concrete transfer action**: what package to carry and where to deliver it. The **technical evidence stays in the technical package**; the Product Owner should not be asked to interpret logs, hashes, code, or specialist findings as part of the transfer.

## Do not manufacture Product Owner work

Do **not manufacture a Product Owner task** when the next action belongs to the Controller, Coding Agent, reviewer, or specialist. Name the **actual responsible role** and its executable next action.

Show Product Owner work only when the Product Owner genuinely owns one of these:

- a product behavior/tradeoff/scope/priority/investment decision;
- final product-visible acceptance;
- the unavoidable Human Courier transfer action.

A transfer does not give the courier authority to approve, reinterpret, or alter the transferred artifact.

## Session Continuity Capsule

Session continuity is separate from Human Courier. Use it when the Product Owner asks to switch conversations/providers, or when the current conversation has become long enough that continued reliance on chat context is no longer a reliable way to carry project state.

After recovering repository-backed state, create or update the compact capsule at `.ai-product/handoffs/latest.md`. The capsule is an **index, not a second source of truth**. Keep only what a fresh capable session needs to locate authority and continue correctly:

- **current product goal** and why it matters;
- **approved decisions** / invariants that should not be reopened without new material evidence;
- **current active change** and plain-language status;
- what is **already verified**;
- what is still **unknown or blocked**;
- **exactly one next action** and the **responsible role**;
- pointers to **authoritative** project/change artifacts;
- the **Product Owner interaction contract**: language, plain-language default, independent judgment, and no technical-choice burden;
- any recent **real-use incident** that still requires follow-up;
- compact **generation** and **repository binding** metadata sufficient to detect that the capsule may be stale.

Do not copy the full conversation or a **transcript** into the capsule. Do not embed **raw test logs**, complete project history, or a second full copy of lifecycle state. Technical package paths may be referenced when needed; technical evidence stays in the authoritative artifacts.

A practical capsule may use this provider-neutral shape:

```markdown
# Session Continuity Capsule
- Product goal: ...
- Why it matters: ...
- Approved decisions/invariants: ...
- Active change / plain-language status: ...
- Already verified: ...
- Unknown or blocked: ...
- One next action: ...
- Responsible role: ...
- Authoritative pointers: ...
- Product Owner interaction contract: ...
- Open real-use incident: ...
- Generated at: ...
- Repository binding: repository identity + observed revision/state marker ...
```

## Fresh-session recovery

A fresh session must recover **repository state first** before treating the capsule as current project state:

1. locate and read the repository-backed project/change authorities;
2. read `.ai-product/handoffs/latest.md` as a compact navigation index;
3. compare the capsule's active change/status/pointers and repository binding with current repository evidence;
4. if they disagree, **prefer the repository**, explain in plain language that the handoff note is outdated, and update/rebuild the capsule after recovery;
5. continue from the recovered truth with one required next action instead of asking the Product Owner to retell project history.

If repository access is unavailable, the capsule may be used only as **unverified context**. Say that the current project state has not yet been confirmed, do not claim repository-backed Git/workflow truth, and **must not mutate lifecycle** state from the capsule alone. The one next action is to regain the authoritative repository/project artifacts or explicitly proceed only with non-mutating discussion.

## Provider-neutral handoff

Keep durable capsule fields **provider-neutral** so the same handoff can move between ChatGPT, Claude, or another capable product/coding agent. Provider-specific commands, tool syntax, model names, or local execution adapters may be secondary operational notes when genuinely useful, but they cannot redefine the product goal, approved decisions, current state, next action, or expected behavior.
