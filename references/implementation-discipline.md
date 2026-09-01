# Implementation Discipline

## Isolation

Use an isolated branch or worktree when the main tree is dirty, unrelated assets exist, or parallel work may overlap. PDC-4.5.2 shared-workspace focus switching never uses stash, destructive reset, deletion, assume-unchanged, skip-worktree, or an alternate index to conceal unverified work. Snapshot-backed parking restores only exact verified change-owned paths to the validated execution base and fails closed on unrelated work or committed shared-HEAD contamination.

## Focus-Bound Mutation

Before any change-specific lifecycle progression, executable-source edit, current-evidence replacement, implementation delegation, or shared-repository mutation, verify the target is `project-state.current_change`. Non-focused unfinished work may be inspected read-only but must not execute in the background. Additional draft scaffolding and narrow deterministic project-state reconciliation are the only coordination exceptions.

Before a blocked change resumes, verify frozen repository identity and exact `baseline_branch_tip_sha`. If the branch tip differs, do not materialize stale implementation; use the immutable technical baseline-refresh path.

## Small Change Standard

One coding-agent task should produce one demonstrable user result and a reviewable file scope. Do not ask for broad cleanup, comprehensive optimization, or opportunistic redesign.

## Test-First Loop

For behavior changes:

1. write the smallest failing test;
2. run it and preserve expected RED evidence;
3. implement the minimum change;
4. run focused GREEN evidence;
5. run every contracted full check;
6. refactor only while green;
7. capture the implementation snapshot.

An exception must be frozen in the contract with reason and approver.

## Evidence

The coding agent reports actual commands, outputs, exit codes, changed files, runtime evidence, and final Git status. Summaries do not replace fresh evidence.

## Stop Conditions

Stop instead of improvising when:

- product rules conflict;
- required files exceed allowed scope;
- baseline or environment differs materially;
- a migration, permission, privacy, or production security decision appears;
- required tests cannot run;
- implementation requires a contract change.
