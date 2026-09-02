# Coding Agent Prompt Pattern

Create a self-contained prompt for Claude Code, Codex, Cursor, or another coding agent. Use the agent recorded in `project-state.json`; do not hard-code one agent name into the workflow.

## Required Sections

1. Repository, branch/worktree, frozen baseline, and an explicit preflight proving this task is the current Focused Change.
2. Task ID, contract version, and digest.
3. Single user-visible result.
4. Current implementation facts.
5. Allowed modification scope.
6. Forbidden changes and protected assets.
7. Required behavior, states, errors, and data results.
8. Test-first requirement or approved exception.
9. Exact focused and full commands.
10. Required implementation report and evidence.
11. Snapshot capture requirement.
12. Stop conditions.

The coding agent must not mutate source, current evidence, or Git on behalf of a non-focused change and must not execute parked work in the background. Run the Focus preflight before change-specific source/Git mutation. The coding agent may report a contradiction but cannot silently alter product behavior or the frozen contract.
