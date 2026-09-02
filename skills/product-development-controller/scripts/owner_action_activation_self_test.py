#!/usr/bin/env python3
"""Deterministic carrier checks for the bounded owner-action runtime repair.

These assertions protect the runtime/interface activation markers and the
existing owner-language firewall. They do not claim model-behavior PASS;
fresh responsibility-separated execution, evaluation, and review remain
required by the frozen Engineering contract.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
SKILL = SKILL_ROOT / "SKILL.md"
OWNER_INTERFACE = SKILL_ROOT / "references" / "product-owner-interface.md"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"required owner-action carrier missing: {path.name}")
    return path.read_text(encoding="utf-8")


def require_all(haystack: str, needles: list[str], context: str) -> None:
    missing = [needle for needle in needles if needle not in haystack]
    if missing:
        raise AssertionError(f"{context} missing required markers: {missing}")


def section(markdown: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", markdown, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing section: {heading}")
    rest = markdown[match.end() :]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def require_consecutive_h2_headings(
    markdown: str, headings: list[str], context: str
) -> None:
    actual = re.findall(r"^##\s+(.+?)\s*$", markdown, re.MULTILINE)
    width = len(headings)
    if not any(actual[index : index + width] == headings for index in range(len(actual))):
        raise AssertionError(
            f"{context} missing required consecutive heading order: {headings}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Accepted for uniform frozen-test invocation; the same carrier checks run.",
    )
    parser.parse_args()

    skill = read(SKILL)
    owner = read(OWNER_INTERFACE)

    require_consecutive_h2_headings(
        skill,
        [
            "Core operating contract",
            "Terminal response and continuation guardrail (non-negotiable)",
            "Trust integrity guardrail (non-negotiable)",
        ],
        "SKILL high-salience terminal guardrail placement",
    )
    terminal_guardrail = section(
        skill, "Terminal response and continuation guardrail (non-negotiable)"
    )
    require_all(
        terminal_guardrail,
        [
            "legitimate report boundary exists before composing",
            "requested Outcome is complete",
            "explicitly asks for a status answer",
            "genuine Product Owner decision, visible acceptance, or unavoidable owner action",
            "genuinely unrecoverable capability, safety, or authority blocker",
            "Internal gate completion, checkpoint recovery, phase transition, dense validation state",
            "recoverable search, index, or retrieval seam",
            "false stops",
            "continue Controller- or tool-owned work before composing",
            "interim update is not a terminal handoff",
            "execution continues in the same run",
            "Degraded capability and executable handoff",
            "minimal owner-relevant projection",
            "reconcile or bypass it backstage",
            "any action-critical value as exact",
            "destination/context, model/reasoning selection, prompt/text/command, file/selection",
            "original characters verbatim",
            "Do not translate, paraphrase, normalize, restructure, or abbreviate",
            "even when the owner surface normally uses another language",
            "Only the surrounding wrapper may be localized",
            "does not create a new Mode, Gate, lifecycle state",
        ],
        "SKILL E27 terminal-response carrier",
    )

    require_consecutive_h2_headings(
        owner,
        [
            "Several unfinished work lines",
            "Terminal boundaries and same-run continuation",
            "Authoritative next actor and executable owner actions",
        ],
        "Product Owner terminal-boundary guidance placement",
    )
    terminal_interface = section(owner, "Terminal boundaries and same-run continuation")
    require_all(
        terminal_interface,
        [
            "minimal owner-relevant projection",
            "Suppress internal execution state",
            "recoverable seam",
            "continue in the same run",
            "reconcile or bypass stale lower-authority projections backstage",
            "complete exact owner-action payload",
            "control-state dump or formatting noise",
            "requested Outcome is complete",
            "explicitly asks for status",
            "progressive disclosure",
        ],
        "Product Owner E27 terminal-boundary guidance",
    )

    require_all(
        skill,
        [
            "### Authority-to-owner action fidelity",
            "derive the real next responsible actor from recovered authoritative project/Work state",
            'A Product Owner asking "what next?" does not make the Product Owner the next actor.',
            "no real stop condition requires owner involvement",
            "do not manufacture a Product Owner task",
            "make the same reply directly executable",
            "exact destination/context",
            "prompt/text/command",
            "visible observation or pass/fail criterion",
            "return condition",
            "reproduce it exactly",
            "generic label or summary",
        ],
        "SKILL owner-action runtime carrier",
    )

    action_section = section(owner, "Authoritative next actor and executable owner actions")
    require_all(
        action_section,
        [
            "authoritative project/Work state",
            "does not itself assign the next step to the Product Owner",
            "no real stop condition requires Product Owner involvement",
            "do not manufacture a Product Owner task",
            "the same reply must carry all action-critical inputs",
            "without a clarification turn solely to discover how to do it",
            "exact destination or context",
            "exact model or reasoning selection",
            "exact prompt, text, or command",
            "reproduced verbatim when authority records it as exact",
            "exact file, artifact, option, or selection",
            "visible observation or pass/fail criterion",
            "return condition",
            "any action-critical value as exact",
            "copy its original characters verbatim",
            "Do not translate, paraphrase, normalize, restructure, or abbreviate",
            "even when the owner surface normally uses another language",
            "Only the surrounding explanatory wrapper may be localized",
            "generic label, shortened paraphrase, or pointer",
        ],
        "Product Owner executable-action guidance",
    )

    require_all(
        owner,
        [
            "## Default presentation layer",
            "Assume a non-technical Product Owner by default",
            "Backstage by default",
            "not optional technical evidence",
            "remains visible in the same reply",
            "Unrelated internal Mode/Focus/branch/commit/hash/workflow/test/history detail",
            "When technical evidence is **explicitly requested**",
            "truly standalone plain-language lead",
            "## Progressive disclosure",
            "Technical evidence remains available",
            "Do not convert a Controller, Builder, reviewer, specialist, or tool action into artificial Product Owner work.",
        ],
        "existing owner-language firewall",
    )

    print("OWNER ACTION ACTIVATION CARRIER SELF TEST PASSED")
    print("- terminal boundaries are classified before response composition")
    print("- false stops and interim updates retain same-run continuation")
    print("- owner projection and stale-projection reconciliation remain scoped")
    print("- next actor is derived from authority; owner work is not manufactured")
    print("- genuine owner actions retain same-reply exact execution payload")
    print("- unrelated internal detail remains behind the owner-language firewall")
    print("- carrier validation only; fresh responsibility-separated behavior evidence remains required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
