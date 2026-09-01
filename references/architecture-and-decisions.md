# Architecture and Decisions

## Minimum Useful Architecture

Use architecture to make implementation understandable, not to decorate documents.

For most product work, start with:

1. **System context:** users, the product, and external systems.
2. **Container/runtime view:** browser, services, databases, queues, external APIs, and ownership boundaries.
3. **Critical flow:** the data and state path for the current feature.

Add component-level detail only when it changes implementation responsibility or risk.

## Architecture Decision Record

Create an ADR only for a consequential choice that future contributors must understand.

Use this structure:

```markdown
# [Decision title]

## Status
Proposed | Accepted | Superseded

## Context and Problem
[why a decision is needed]

## Decision Drivers
- [constraint or quality]

## Considered Options
- [option]

## Decision Outcome
Chosen: [option], because [reason].

## Consequences
- Positive:
- Negative:

## Confirmation
[how the decision will be verified]
```

Do not turn routine implementation choices into ADRs.

## Product Owner Boundary

The product owner decides user behavior, business tradeoffs, acceptable risk, and scope. The controller resolves ordinary technical choices from evidence. Escalate only choices that materially change product behavior, cost, time, data handling, or irreversible architecture.
