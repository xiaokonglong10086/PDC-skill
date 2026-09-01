# PDC — Product Development Controller

PDC helps non-technical and weakly technical Product Owners control persistent digital-product development without becoming the Git, log, or recovery operator. It keeps product work outcome-first rather than implementation-first, with one advancing Work Focus and explicit routes through Explore, Preview, and Engineering.

Evidence & Authority is a separate control layer. Engineering boundaries are frozen before implementation; a Builder cannot self-approve; and every technical completion claim is bound to an exact deliverable identity and independent verification. Technical PASS remains distinct from Product Owner visible acceptance. Integration and closure preserve recoverable continuity so work can resume from durable repository evidence.

Software/PDC is the implemented strict, repository-backed Engineering profile. This repository is a curated public portfolio snapshot of mature capability, not private development authority. It has no automatic private-to-public sync, and no open-source license is granted.

## Repository map

- `SKILL.md` — controller entry point and operating contract
- `references/` — product, authority, workflow, review, and recovery rules
- `scripts/` — deterministic lifecycle, validation, evidence, and public self-test tooling
- `assets/` — project templates and model-behavior evaluation assets
- `PORTFOLIO.md` — design rationale and capability overview
- `PUBLIC_VERIFICATION.md` — curated standalone public verification suite and commands
- `PUBLIC_RELEASE_SCOPE.md` — the public/private release boundary

## How to inspect

1. Read `SKILL.md` for the control model and routing rules.
2. Follow its direct references for the relevant mode or lifecycle phase.
3. Run `python scripts/audit_skill_package.py` to validate the curated package boundary.
4. Follow `PUBLIC_VERIFICATION.md` to run the complete standalone public verification suite.

