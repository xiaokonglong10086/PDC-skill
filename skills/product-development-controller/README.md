# PDC Skill package

This directory contains the runtime **Product Development Controller** Skill that ships inside the public `PDC-skill` repository.

PDC controls long-running AI product development around executors such as Codex, Claude Code and Cursor. Its core guarantees include outcome-first routing, exactly one advancing Work Focus, Explore / Preview / Engineering mode selection, frozen Engineering completion boundaries, independent exact-target verification, Product Owner acceptance separation, and durable recovery.

## Runtime entrypoint

- [`SKILL.md`](SKILL.md) — main Skill contract
- [`references/`](references/) — architecture, authority, routing, review, acceptance and recovery rules
- [`scripts/`](scripts/) — deterministic lifecycle, evidence, verification and recovery tooling
- [`assets/`](assets/) — project templates and model-behavior evaluation assets

## Public release context

This Skill directory is distributed as part of the public open-source PDC Beta. Repository-level installation, CI, release, security, contribution and support documentation live at the repository root.

The full public/private boundary is defined by [`../../PUBLIC_RELEASE_SCOPE.md`](../../PUBLIC_RELEASE_SCOPE.md), and the current public verification contract by [`../../PUBLIC_VERIFICATION.md`](../../PUBLIC_VERIFICATION.md).

## License

This package is distributed under the repository's [MIT License](../../LICENSE).
