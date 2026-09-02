# Strategic Workpath

## Purpose

Use this reference when the focused Work is complex enough that individual locally sensible next actions could drift away from the Outcome.

A **Strategic Workpath** is a Strategy-level **Work-control planning projection** derived from the existing kernel concepts: Outcome, Work, Mode, Control Decision, and Evidence & Authority. It relates the one required next action to a credible end-to-end route.

It is deliberately **not** any of the following:

- not a Kernel concept (the kernel remains exactly five concepts);
- not a Mode of any kind — the Modes remain exactly Explore / Preview / Engineering;
- not a lifecycle state or workflow status;
- not a workflow engine, not a scheduler, not a dependency graph, and not a Work state machine;
- not Product Truth and not a second mutable source of completion authority.

## Durable Workpath continuity (M3 runtime)

Since M3 (V2 Durable Authority and Work Continuity), complex/material Workpaths use a **durable Work-control projection** managed by `workpath_continuity.py` under the dedicated Controller-state namespace `.ai-product/workpaths/`:

- the current Strategic Workpath projection (current route, active waypoint / current position, major waypoints, ordering rationale, advancement/exit conditions, provisional future portions, route uncertainty, source authority references, revision reason) is durably preserved as project-control state;
- a revision creates a **new current revision** and preserves the old revision as a historical planning record with prior-version linkage — old revisions are never silently overwritten;
- a new session recovers the current route, active waypoint, and revision lineage from the durable record (repository-backed Software/PDC profile: see `profile-software-pdc.md` recovery path);
- **stale-path handling**: when current Outcome / Work / authoritative state invalidates a route-driving assumption, or the active waypoint can no longer reasonably advance the Outcome, the current Workpath is marked **STALE** with an explicit diagnosis. The old route is never silently continued; continuation happens only through an explicit Workpath revision/replan with provenance. Never newest-file-wins, latest-timestamp-wins, chat-summary-wins, or agent guess. A frozen Engineering completion boundary is never silently mutated — frozen scope changes only through the authorized revision path of the governing Development Profile.

The Workpath remains a Work-control planning projection: not a Kernel concept, not a Mode, not a lifecycle state, not a workflow engine/scheduler/dependency graph, not Product Truth, and not a second mutable source of completion authority.

## When to form a Workpath

Form a proportionate Workpath when the focused Work is complex: several major steps, an unfamiliar domain, material investment, a long horizon, or several competing partial directions.

Ordinary low-risk reversible work that is already decision-ready does not need a Workpath. Default to direct action there. Proportionality is the rule: the route description must not cost more control burden than the complexity it organizes.

## Route shape

A proportionate Workpath contains, at the level the current evidence supports:

1. **Outcome / Intent basis** — the approved Outcome and constraints the route serves.
2. **Major waypoints** — the few substantial positions the work must pass through, named by what becomes true, not by ceremony.
3. **Ordering rationale** — why this waypoint sequence is credible now (dependency, evidence order, risk reduction, value order).
4. **Current position** — which waypoint is active and what is already established.
5. **Material advancement / exit conditions** — what observable evidence or decision shows a waypoint is genuinely advanced or exited.
6. **Provisional future portions** — later waypoints marked explicitly as provisional; they are expectations, not commitments.
7. **Evidence and professional-practice basis** — the observations, decisions, and material professional practice that shaped the route.

The route is a projection, not a promise. Every portion beyond the active waypoint remains revisable by evidence.

## One required next action discipline

The single required next action must do exactly one of:

- **advance the current credible Workpath** — it moves the active waypoint toward its exit condition;
- obtain **decisive evidence** the route needs before the next commitment (including Explore/Preview evidence when reality must answer);
- resolve a **blocker** that stops the route from advancing;
- explicitly **replan** when evidence shows the current route is no longer credible.

If a proposed next action cannot be explained in one of these four ways against the active Workpath, treat that as a route-discipline problem before executing it.

Replanning revises the projection. It never silently moves a frozen Engineering completion boundary: frozen scope changes only through the authorized revision path of the governing Development Profile.

## New ideas and evidence: five-way classification

When a material new idea, request, or evidence item appears, classify it as exactly one of:

1. **current path progress** — it advances the active waypoint; fold it into the current next action;
2. **known later path** — it belongs to a later waypoint; record it there without advancing it now;
3. **route revision** — it changes the credible route; update the Workpath explicitly;
4. **separate Work** — it serves a different Outcome; keep it as a separate unfinished Work item, parked unless priority legitimately changes Focus;
5. **does not serve the current Outcome** — acknowledge and do not absorb it.

Future waypoints do not automatically become Work. A waypoint becomes Work only through an explicit Focus/priority decision under the existing Work-control rules, and there remains exactly one advancing Work Focus.

## Local-optimum and path-deviation detection

Detect and interrupt locally reasonable but globally drifting behavior. A confirmed local-optimum or path-deviation trigger means the route, not the effort, must be questioned. Trigger signs include:

- the current action cannot explain how it advances the active waypoint or the Outcome;
- the action does not reduce the real gating risk that currently matters;
- repeated optimization of a secondary concern while the active waypoint stalls;
- sunk-cost continuation: continuing because effort was already spent, not because the route is credible;
- entering expensive Engineering while material direction uncertainty is still unresolved;
- several consecutive local actions that never approach the active waypoint's exit condition.

When a trigger is confirmed, redirect the one required next action or explicitly replan. Do not answer drift with more process.

## Professional practice as route evidence

When mature professional practice can materially affect sequencing, omissions, risk, or investment, use it as route evidence:

- mature workflows and practices;
- standards, regulations, and constraints;
- mature products and substitutes;
- open-source, tool, and platform patterns;
- common failure modes;
- specialist checkpoints;
- real-environment validation requirements.

Adapt it through **Reuse**, then **Adapt**, then **Innovate** only when a demonstrated gap remains.

Professional practice is evidence and prior, not Product Truth and not a mandatory process authority. Do not copy an entire professional methodology into the kernel, and do not force its vocabulary or stage names onto the Product Owner.

## Product Owner route disclosure

When route context materially helps the Product Owner understand or decide, present it in product language:

`overall route -> current position -> why this now -> one next action -> provisional future`

Mark provisional portions plainly. Ordinary replies are not required to display the full route; disclose proportionally, following the adaptive Product Owner collaboration rules.

## Boundary with Engineering authority

The Workpath never rewrites frozen Engineering scope, never approves its own advancement, and never substitutes for Evidence & Authority. Technical PASS, Product Owner acceptance, and closure remain owned by the existing completion law and the governing Development Profile.

## Journaled Workpath publication law

Workpath publication is append-only and owner-bound:

- `MARK_STALE` is legal exactly when `explicit_control_decision` is null;
- `EXPLICIT_REBUILD` is legal exactly when it carries an activated `ControlDecisionRefV1` object;
- `projection_update_id` binds the typed owner event, expected prior revision, binding version, effect, and explicit decision digest;
- publication converges through `PREPARED`, `CANDIDATE_MATERIALIZED`, and `POINTER_PUBLISHED` with CAS checks before materialization, before pointer publication, and after publication;
- current owner and authority are revalidated before pointer publication;
- a newer explicit decision-bound route wins a race with stale repair and is neither overwritten nor duplicated.

`FINDINGS` makes an old projected next action non-executable and permits deterministic projection repair only. `FAIL_CLOSED` and `ERROR` do not select a Focus owner, create a formal route successor, advance the pointer, or revive a stale action.
