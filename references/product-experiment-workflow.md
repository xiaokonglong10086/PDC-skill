# Product Experiment Workflow

## Purpose

Use this reference only when the Controller has already classified the current optimization mode as **Preview**.

Preview optimizes for the fastest reliable acquisition of real product or user evidence about one clear Primary Unknown. It is intentionally lighter than Engineering, but it is not unbounded hacking and it does not waive safety, privacy, data-integrity, or specialist-review boundaries that are necessary for the experiment to be credible.

PDC-4.5 implements Preview work itself. It does **not** implement Preview -> Engineering Promotion Gate, Direct Engineering transition, Owner Override, production qualification of Preview code, Product Truth, Engineering Facts, Constitution, or a formal Preview lifecycle state machine.

## Entry guard

Before running a Preview cycle, verify all of the following:

- the current mode is Preview because the current optimization objective is product learning;
- no already-active Engineering task is being silently weakened, abandoned, or converted into Preview;
- the Controller can state one Primary Unknown;
- a smallest complete user loop can be described;
- meaningful evidence can be described;
- temporary shortcuts and exclusions can be stated without invalidating the evidence;
- safety, privacy, data-integrity, access, and irreversible-action boundaries are explicit when relevant.

If an active Engineering task exists, its frozen workflow remains authoritative. A product issue discovered during Engineering follows the existing Engineering -> Product Decision rule; PDC-4.5 does not silently switch that task into Preview.

## One Primary Unknown

Every Preview cycle has **exactly one Primary Unknown**: the uncertainty whose answer determines whether the current experiment succeeded.

Rules:

- preserve it until the cycle is explicitly closed or reframed;
- do not let a new idea, reviewer suggestion, incidental defect, or product-owner enthusiasm silently replace it;
- record every other discovery as a **Secondary Observation** in the **Learning Ledger**, preserving its evidence and limitations;
- promote a Secondary Observation into a later Primary Unknown only through an explicit later choice;
- if a discovery makes the current experiment incapable of answering the Primary Unknown, explicitly reframe or close the cycle rather than drifting scope.

The product owner's latest preference is decision input, not retroactive evidence. A statement such as "I think this is validated" may be recorded as owner interpretation, but it does not become Validated Learning unless the evidence required by the Primary Unknown exists.

## Smallest complete user loop

Define the smallest end-to-end experience a user can actually complete that is sufficient to answer the Primary Unknown.

Optimize for a complete observable user experience, not minimum code or minimum number of screens.

Example:

`training material -> three questions -> game interaction -> result`

Do not expand the experiment merely because future production capabilities such as accounts, multi-tenant administration, rankings, analytics, or production infrastructure may eventually be needed.

## Cheapest credible experiment

Choose the lowest-cost method that can still produce credible evidence for the Primary Unknown.

Permitted methods include:

- manual simulation;
- mock data;
- static pages;
- AI-generated prototypes;
- lightweight scripts;
- temporary local storage;
- partial automation;
- human review;
- a bounded end-to-end Demo built by a Coding Agent.

A shortcut is acceptable only when it does not distort the user behavior being observed and does not create unacceptable safety, privacy, data-integrity, or irreversible-operation risk. Every accepted manual, mock, or provisional shortcut must be explicitly labeled temporary. The shortcut itself is not production-readiness evidence and must not be presented as proof that the future production workflow, automation, architecture, or operational controls are ready.

A future Engineering limitation that is not causal to the current Preview purpose does not invalidate the experiment.

## Fast Preview execution profile

**Fast Preview** is an execution profile inside Preview. Select it only when **code or a runnable artifact is the cheapest credible evidence** for the current Primary Unknown. Static/manual simulation, concierge evidence, or another cheaper credible method remains valid when it can answer the question. Fast Preview never creates a fourth mode and is still Preview.

### Minimum Credible Fidelity

Before building, state the **Minimum Credible Fidelity** required by the Primary Unknown. Make real only the dimensions whose realism is causal to the evidence; keep the rest explicit mocks, temporary shortcuts, or exclusions. Relevant dimensions can include:

- **interaction / flow** -- navigation, timing, state changes, or user actions that must behave realistically;
- **visual / content** -- appearance or content quality only when it can change the observed behavior;
- **data** -- real or representative data only when the data itself is causal to the conclusion;
- **AI / model behavior** -- representative real model behavior and credible settings when actual AI quality is the question; canned output is not evidence for a model-quality Primary Unknown;
- **device / environment** -- realistic browser, simulator, device, input or operating context when that environment can change the result;
- **human / operational step** -- real people or operational handoffs when the human process is itself causal.

Do not increase fidelity because the Coding Agent can. Increase it only when lower fidelity would make the evidence misleading. Label all non-causal mocks and temporary shortcuts so they cannot be mistaken for production-readiness evidence.

### Fast Preview Build Brief and delegation

Do not create a second contract-like artifact. Reuse the existing **Preview Implementation Brief** as the **Fast Preview Build Brief** and add only the execution details needed to preserve evidence credibility:

- which fidelity dimensions must be real and which are explicit mocks/shortcuts;
- the critical evidence loop that must run;
- any causal browser/device/model/data capability that must be exercised;
- the observable handoff point for representative use;
- a recoverable-version expectation for meaningful stable/decision points.

Prefer direct delegation and **platform-native** execution, preview/testing, version history, checkpoints, branches/worktrees or equivalent capabilities when they are actually available. PDC owns the learning question, fidelity boundary and evidence semantics; the Coding Agent/app-builder owns ordinary framework, file and runtime mechanics. Do not invent a PDC-owned preview host, browser framework, checkpoint database, worktree manager or provider adapter layer.

Use **Human Courier** only when direct transfer/delegation is unavailable, and then use it only as the existing transfer action. Do not ask the Product Owner to carry ordinary technical plumbing when another role can act directly.

### Lightweight credibility verification before evidence use

Before Product Owner or representative-user evidence is collected, verify enough of the returned prototype to trust the experiment:

1. **startup / render** succeeds in the relevant environment;
2. the **critical end-to-end loop** required by the Primary Unknown works;
3. any browser/device/model/data/human capability causal to the Primary Unknown is exercised realistically when the capability exists;
4. only verification actually executed may be claimed.

Use realistic browser/device checks when those dimensions are causal and the capability is available. If a causal capability is unavailable, state the evidence limitation or escalate it; do not fabricate verification. the Preview rule is: **do not import routine Engineering-grade QA** such as full CI, production security hardening, reliability qualification or deployment proof unless that specific property is causal to Preview evidence credibility.

### Meaningful recoverable checkpoints

Retain a **meaningful recoverable checkpoint** when a state is valuable to preserve, especially:

- the first credible complete loop;
- a Product Owner/current-best accepted Preview state;
- before a risky rebuild/regeneration when the prior state may still contain useful evidence;
- a retained/finalization state that should survive model/session replacement.

Prefer platform-native history/checkpoints/versioning. If those capabilities are unavailable and code lives in a repository, use a lightweight Git snapshot/commit only when needed to retain the meaningful state. the checkpoint rule is: **do not checkpoint every trivial edit** or expose checkpoint mechanics to the Product Owner unless they affect the product decision.

### Patch versus rebuild by learning yield

For a bounded local defect or request, **patch forward** while the prototype structure remains fit for the current evidence purpose. Reuse **Prototype Iteration Review** when substantial revisions accumulate or regression patterns appear. Rebuild/regenerate when regression chains, prototype debt or structure/fidelity drift mean **maintenance cost exceeds expected learning yield**.

Treat an **established repeated regression/debt chain** as enough evidence to make that rebuild decision when fixes repeatedly break other working behavior and **confirmed or accepted behavior keeps disappearing**, while the **Primary Unknown** and **Decision Rule** remain unchanged. In that case, first make a bounded summary of learning already obtained, preserve the confirmed behavior and evidence logic, retain the latest meaningful recoverable state when useful, then **choose rebuild/regenerate** as the smallest honest next move; **do not defer that choice** to another abstract cost/benefit review. This is evidence-based: **revision count alone is not a rebuild threshold**. If material regression/debt is absent and expected learning yield remains high, continuing to patch can remain correct even after three or more substantial revisions.

A rebuild must preserve the **Primary Unknown**, **Decision Rule**, **confirmed behavior**, and evidence logic unless the experiment is explicitly reframed. Preserve the latest meaningful recoverable state before a risky rebuild when useful. A rebuild remains Preview; code volume or a clean regeneration does not turn it into Engineering.

### Prototype Finalization Record

At a meaningful retained/current-best/finalization point, create or update `.ai-product/experiments/<experiment-id>/prototype-record.md`. This is lightweight Preview persistence, not a new lifecycle state or approval artifact. Record only what is useful for future evidence recovery or reconstruction:

- current purpose and Primary Unknown;
- retained-version summary and meaningful checkpoint/recovery reference;
- confirmed behavior, with evidence/provenance and decision authority kept distinct;
- temporary mocks, manual steps and provisional shortcuts;
- known limitations and unvalidated items;
- run/view hint when available;
- optional reconstruction prompt or hint when useful;
- explicit authority note: **Preview evidence only; not production qualification or Engineering reuse approval.**

A polished prototype, positive stakeholder reaction, or a complete-looking record cannot qualify production/customer deployment or automatically approve reuse of the prototype code or architecture. The Preview cycle may at most end as the existing `Engineering Candidate` outcome for a later, separately authorized evaluation.

## Preview Implementation Brief

When code is useful, prefer one relatively large but bounded end-to-end Preview brief over default Engineering-sized fragmentation.

A Preview Implementation Brief contains:

1. **Current product purpose** -- what this experiment is trying to learn.
2. **Primary Unknown** -- exactly one.
3. **Smallest complete user loop** -- the full experience the user must be able to complete.
4. **Required user experience** -- what must be real enough to produce meaningful behavior evidence.
5. **Evidence to observe** -- the concrete observations needed from use.
6. **Allowed temporary shortcuts** -- mock data, manual steps, temporary storage, provisional architecture, or similar shortcuts that do not invalidate evidence.
7. **Explicit exclusions** -- capabilities intentionally not built for this experiment.
8. **Safety / privacy / data boundaries** -- protections that cannot be bypassed merely because this is Preview.
9. **Handoff point** -- the observable point at which the build is ready for product-owner experience and representative use.

The Preview Implementation Brief is **not an Engineering frozen contract**. It does not create Engineering review gates, immutable per-slice completion boundaries, production deployment requirements, or production qualification by default.

The Preview may be rebuilt, regenerated, or implemented differently when that is faster for learning, provided the Primary Unknown and evidence logic are not silently changed.

## Evidence and interpretation separation

Record observation before interpretation.

Each evidence entry should contain:

- Evidence ID;
- Date;
- Source and user type;
- Environment or context;
- Observed fact;
- Relation to the Primary Unknown;
- What the observation supports or contradicts;
- Limitation / confidence;
- Product-owner interpretation or preference, when present, in a separate field;
- Resulting learning candidate.

Do not rewrite interpretation as observation. In particular:

- "The product owner likes it" is owner feedback.
- "Three representative employees completed the loop without assistance" is observed user evidence.

The first statement cannot silently substitute for the second when the Primary Unknown concerns real-user behavior.

## Lightweight persistence

Preview persistence is file-based and intentionally lightweight. It does not create a formal Preview state machine.

Use:

```text
.ai-product/
|-- learning-ledger.md
`-- experiments/
    `-- <experiment-id>/
        |-- experiment-brief.md
        |-- evidence.md
        |-- iteration-review.md   # only when triggered
        `-- prototype-record.md   # Fast Preview retained/finalization points only
```

Canonical paths are `.ai-product/learning-ledger.md`, `.ai-product/experiments/<experiment-id>/experiment-brief.md`, `.ai-product/experiments/<experiment-id>/evidence.md`, optional `.ai-product/experiments/<experiment-id>/iteration-review.md`, and optional `.ai-product/experiments/<experiment-id>/prototype-record.md` for a retained Fast Preview state.

### experiment-brief.md minimum fields

- Experiment ID;
- Status: `active` or `closed` as a descriptive record only, not workflow state;
- Current purpose;
- Target user / problem;
- Primary Unknown;
- Smallest Complete User Loop;
- Meaningful Evidence;
- Temporary Shortcuts;
- Explicit Exclusions;
- Safety / Privacy / Data Boundaries;
- Product Decision Checkpoint, if any;
- Preview Implementation Brief, if code is useful;
- Secondary Observations;
- Current Next Action;
- Cycle Decision.

### evidence.md minimum fields

For each evidence entry record:

- Evidence ID;
- Date;
- Source / user type;
- Environment;
- Observed Fact;
- Relation to Primary Unknown;
- Supports / Contradicts;
- Limitation / Confidence;
- Product-owner Interpretation, if any;
- Resulting Learning Candidate.

### New-session recovery order

When recovering Preview work in a new session:

1. read the normal project and Engineering workflow state first so an active Engineering task is not silently replaced;
2. read `.ai-product/learning-ledger.md` when it exists;
3. inspect `.ai-product/experiments/*/experiment-brief.md` and identify the single descriptive `Status: active` experiment for the current focus;
4. read that experiment's `Primary Unknown`, `Smallest Complete User Loop`, `Meaningful Evidence`, `Secondary Observations`, `Current Next Action`, and latest `evidence.md` entries;
5. resume from the recovered evidence state before interpreting the newest user message as a new focus.

If no active experiment exists, do not invent one from stale notes. If more than one active experiment appears for the same project focus, treat that as an inconsistency and resolve the single focus before continuing.

## Learning Ledger

The long-term Learning Ledger stores product learning, not generic meeting notes and not Engineering completion criteria.

### Canonical long-term categories

- `Validated Learning`
- `Rejected Hypothesis`
- `Open Question`
- `Engineering Requirement Candidate`

Do not add a fifth long-term category in PDC-4.5.

Each ledger item records:

- ID;
- Type, using exactly one canonical category above;
- Statement;
- Provenance / evidence;
- Affected experiment;
- Confidence / limitation;
- Blueprint impact: `yes`, `no`, or `undecided`;
- Secondary Observation: `yes` or `no`;
- Authority Note.

Rules:

- **Validated Learning** requires explicit supporting evidence appropriate to the question being answered.
- **Rejected Hypothesis** records a prior assumption contradicted by evidence.
- **Open Question** preserves unresolved uncertainty instead of allowing optimism to erase it.
- **Engineering Requirement Candidate** is candidate evidence only. It has **no Engineering completion authority** until a later explicit product decision or Promotion Gate makes it formal in approved product truth, specification, constitution, or frozen Engineering contract.
- Record every Secondary Observation in the Learning Ledger, choose the appropriate one of the four canonical categories for its current evidence state, mark `Secondary Observation: yes`, and preserve its evidence and limitations. Its presence does not silently change the current Primary Unknown, current Preview scope, or Engineering completion criteria unless it makes the current experiment unable to answer the Primary Unknown.
- Product-owner preference or enthusiasm can be recorded as interpretation, but cannot by itself rewrite an Open Question into Validated Learning.

## Prototype Iteration Review

Trigger a Prototype Iteration Review after roughly two to three substantial Preview revisions, or earlier when regression patterns appear.

This is a **review trigger, not a hard iteration cap**. Two or three revisions can trigger review, but they do not by themselves force a rebuild.

Before choosing the next path, summarize the product learning already obtained from the current Preview: what has been validated, what has been rejected, and what remains open. Preserve the current Primary Unknown, Decision Rule, confirmed behavior, and evidence logic unless the experiment is explicitly reframed. When that summary confirms the established repeated regression/debt chain described above, choose rebuild/regenerate in this review rather than scheduling another review to decide whether the already-observed chain is costly enough.

Review:

- what new product learning the latest revisions produced;
- whether current failures are product questions or accumulated prototype architecture debt;
- whether regressions are appearing, such as `fix A -> break B -> rewrite C`;
- whether another patch is likely to create material learning;
- the current maintenance cost of preserving and repairing the prototype;
- whether learning yield is now lower than prototype maintenance cost.

If learning yield remains high, continuing Preview can be justified even after a third major revision.

If maintenance cost exceeds learning yield, stop incremental patching. Only after that learning summary, choose the smallest honest next move:

- rebuild/regenerate the Preview while preserving the Primary Unknown and evidence logic;
- Return to Explore;
- Stop;
- mark the behavior as Engineering Candidate for later Promotion Gate evaluation.

Do not call a rebuild "Engineering" merely because it contains code.

## Full Resource Escalation Packet

When a technical, resource, access, budget, evidence, or specialist issue appears, do not summarize it as "too complex" or "cannot do". Build the full packet.

Required fields:

1. **Current goal** -- what the current experiment is trying to accomplish.
2. **Verified facts** -- only facts supported by current evidence.
3. **Exact blocker** -- the precise obstacle.
4. **Impact on current purpose** -- including an explicit causal-to-current-loop judgment.
5. **Attempts already made** -- concrete attempts and outcomes.
6. **Decision needed** -- exactly one classification from the list below.
7. **Resource needed** -- exactly one classification from the list below.
8. **Executable handoff / current-loop consequence** -- one concrete handoff when blocked, or the explicit instruction to continue the current loop when the issue is non-causal.

### Decision-needed classifications

- `product decision`
- `technical judgment`
- `external evidence`
- `budget/time choice`
- `specialist approval`

### Resource-needed classifications

- `person`
- `tool`
- `data`
- `budget`
- `access`
- `time`

Causality rule:

- if the blocker is causal to the current user loop or necessary evidence, stop only the affected action and perform the executable handoff;
- if the blocker is not causal to the current Preview purpose, record it as a future concern and continue the current experiment;
- do not let a future production Engineering problem invalidate a Preview that is fit for its current purpose.

Professional safety, privacy, authorization, tenant-isolation, data-integrity, compliance, or irreversible-operation concerns that are necessary for the current experiment require the appropriate specialist judgment. Product-owner preference cannot waive them.

## Cycle decision

A meaningful PDC-4.5 Preview cycle ends as exactly one of:

- `Continue Preview`
- `Return to Explore`
- `Stop`
- `Engineering Candidate`

These are product-experiment outcomes, not new `workflow-state.json` statuses.

`Engineering Candidate` means the product behavior appears sufficiently supported to request a future promotion evaluation. PDC-4.5 stops there.

PDC-4.5 must **not**:

- execute Preview -> Engineering Promotion Gate;
- execute Direct Engineering transition;
- execute Owner Override;
- declare Preview code production-ready;
- qualify Preview code for reuse in production;
- silently mutate Engineering workflow state because the owner says "engineer it now".

## Product Owner Control Card during Preview

Keep the PDC-4.4 Control Card as the default product-owner interface. During Preview, make these points concrete:

- **Current mode:** Preview.
- **Current purpose:** the current experiment outcome.
- **Primary Unknown:** exactly one.
- **Already verified:** observed evidence only.
- **Still insufficient:** the exact evidence still missing.
- **Fitness for Current Purpose:** whether the current prototype is sufficient for this experiment, separately from production fitness.
- **One required next action:** the next executable experiment step.
- **Responsible role:** the person or role who acts next.
- **Advancement condition:** the observation or decision that closes the current step.

Do not expose Git, hashes, schemas, frameworks, protocols, databases, or raw logs unless they materially change the product decision or the owner explicitly asks.

## Engineering boundary

Preview is lighter because its objective is learning, not because Engineering standards were weakened.

Once work is in Engineering, keep the existing strict lifecycle intact:

`specification -> design -> frozen contract -> implementation -> Controller verification -> bounded review -> product acceptance -> integration -> closure`

A Preview's success validates product behavior and learning. It does not automatically validate its code, architecture, security, reliability, maintainability, migrations, deployment model, or production readiness.
