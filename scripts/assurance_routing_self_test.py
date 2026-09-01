#!/usr/bin/env python3
"""Focused invariant checks for the frozen GF-M2 V2 Assurance Routing authority.

Protects the frozen GF-M2 contract v1 completion boundary deterministically:
assurance routing is a Control Decision derivative that tailors additive
assurance requirements only after the current Control Decision has already
selected formal Engineering for the Work/claim. It never decides whether to
enter Engineering, whether research is needed, whether to enter Preview,
whether Product Owner clarification is needed, or whether evidence suffices
for a product-direction decision; those remain with Decision Readiness /
Mode routing. This test asserts the Universal Assurance Floor (non-weakenable
ten items), Baseline + additive tailoring, the three routing inputs
(Consequence / Reversibility / Specialist Boundary), the AR-01..AR-06
representative scenarios, specialist fail-closed, false escalation / false
de-escalation guards, the Decision Readiness / Assurance Routing / Review
Assurance Routing responsibility separation, the no-fourth-Mode/state/engine/
score/class/Profile boundary, and the Product Owner burden boundary.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
SKILL = SKILL_ROOT / "SKILL.md"
ASSURANCE = SKILL_ROOT / "references" / "assurance-routing.md"
DECISION_READINESS = SKILL_ROOT / "references" / "decision-readiness-routing.md"
REVIEW_ASSURANCE = SKILL_ROOT / "references" / "review-assurance-routing.md"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(
            f"required GF-M2 assurance-routing authority file missing: {path.relative_to(SKILL_ROOT)}"
        )
    return path.read_text(encoding="utf-8")


def require_all(haystack: str, needles: list[str], context: str) -> None:
    missing = [needle for needle in needles if needle not in haystack]
    if missing:
        raise AssertionError(f"{context} missing required markers: {missing}")


def require_absent(haystack: str, needles: list[str], context: str) -> None:
    present = [needle for needle in needles if needle in haystack]
    if present:
        raise AssertionError(f"{context} contains forbidden markers: {present}")


def require_absent_heading(haystack: str, pattern: str, context: str) -> None:
    if re.search(pattern, haystack, re.MULTILINE):
        raise AssertionError(f"{context} introduces a forbidden mechanism heading")


def main() -> int:
    parser = argparse.ArgumentParser(description="GF-M2 V2 Assurance Routing invariant checks.")
    parser.add_argument("--smoke", action="store_true", help="Accepted for uniform frozen-test invocation; same checks run.")
    parser.parse_args()

    skill = read(SKILL)
    assurance = read(ASSURANCE)
    decision = read(DECISION_READINESS)
    review = read(REVIEW_ASSURANCE)

    # --- Formal Engineering scope precondition -----------------------------------
    require_all(
        assurance,
        [
            "after the current Control Decision has already selected formal Engineering",
            "additional assurance",
        ],
        "formal Engineering scope precondition",
    )

    # --- Boundary regression guard ------------------------------------------------
    # For Work not yet confirmed for Engineering, assurance routing never routes the
    # Work itself; existing Decision Readiness / Mode routing owns those decisions.
    require_all(
        assurance,
        [
            "does not force Engineering",
            "does not require research",
            "does not require Preview",
            "does not require Product Owner clarification",
        ],
        "boundary regression guard",
    )

    # --- Engineering-tailoring positive case --------------------------------------
    require_all(
        assurance,
        [
            "already selected formal Engineering",
            "Consequence",
            "Reversibility",
            "Specialist Boundary",
        ],
        "Engineering-tailoring positive case",
    )

    # --- Responsibility separation -------------------------------------------------
    require_all(
        assurance,
        [
            "Decision Readiness",
            "which evidence/action route",
            "Review Assurance Routing",
            "reviewer",
        ],
        "responsibility separation",
    )
    require_all(
        skill,
        ["references/assurance-routing.md"],
        "SKILL assurance-routing reachability",
    )
    # Existing routing authorities stay reachable: Decision Readiness directly from the
    # SKILL entrypoint, Review Assurance Routing from the new assurance authority (which
    # references rather than duplicates the reviewer taxonomy).
    require_all(
        skill,
        ["references/decision-readiness-routing.md"],
        "SKILL Decision Readiness reachability",
    )
    require_all(
        assurance,
        ["references/review-assurance-routing.md"],
        "assurance-routing references Review Assurance Routing",
    )

    # --- Universal Assurance Floor (non-weakenable) --------------------------------
    require_all(
        assurance,
        [
            "Universal Assurance Floor",
            "completion boundary",
            "redefine Intent",
            "self-approve",
            "independent",
            "binds the actual deliverable",
            "Product Owner acceptance",
            "specialist/safety",
            "finish line",
            "delivery/integration",
            "recoverable",
        ],
        "universal assurance floor",
    )
    require_all(assurance, ["never removes"], "floor non-weakenable wording")

    # --- Baseline + additive tailoring ----------------------------------------------
    require_all(
        assurance,
        [
            "Baseline + additive tailoring",
            "never removes independent verification or evidence",
            "verification depth",
            "verification method",
            "independent checks",
            "specialist involvement",
            "behavior-evaluation depth",
            "isolation",
            "rollback/checkpoint",
            "delivery",
            "production/runtime",
        ],
        "additive tailoring dimensions",
    )

    # --- Routing inputs --------------------------------------------------------------
    require_all(assurance, ["Consequence", "Reversibility", "Specialist Boundary"], "routing inputs")

    # --- Specialist boundary fail-closed ----------------------------------------------
    require_all(
        assurance,
        [
            "fail closed",
            "no specialist is available",
            "does not substitute specialist judgment",
        ],
        "specialist fail-closed",
    )

    # --- False escalation / false de-escalation ---------------------------------------
    require_all(
        assurance,
        [
            "false escalation",
            "surface complexity",
            "false de-escalation",
            "small diff",
        ],
        "false escalation/de-escalation guards",
    )

    # --- Anti-drift: Control Decision derivative, never a mechanism --------------------
    require_all(
        assurance,
        [
            "Control Decision derivative",
            "not a Mode",
            "not a lifecycle state",
            "not a workflow engine",
            "not an approval ladder",
            "not a universal stage router",
            "not a generic risk-management subsystem",
            "must never become",
            "entry gate",
            "second Decision Readiness",
            "risk score engine",
            "assurance class system",
            "second workflow engine",
        ],
        "anti-drift boundary",
    )
    # No mechanism section may be introduced under the new authority.
    require_absent_heading(
        assurance,
        r"^#+\s*(?:The\s+)?Assurance\s+(?:Mode|Lifecycle|Level|Class|Score)\s*$",
        "assurance-routing.md",
    )
    require_absent_heading(
        assurance,
        r"^#+\s*.*(?:approval ladder|stage router|risk score|assurance class system)\s*$",
        "assurance-routing.md",
    )
    # The SKILL entrypoint introduces none of the forbidden mechanism vocabulary.
    require_absent(
        skill,
        [
            "Assurance Mode",
            "assurance lifecycle",
            "assurance level",
            "assurance class",
            "assurance score",
            "risk score",
            "approval ladder",
            "stage router",
        ],
        "SKILL forbidden mechanism vocabulary",
    )

    # --- Representative scenarios AR-01..AR-06 -----------------------------------------
    require_all(assurance, [f"AR-{i:02d}" for i in range(1, 7)], "representative scenario coverage")
    require_all(
        assurance,
        [
            "cheap assurance",
            "standard",
            "isolation",
            "specialist",
            "false escalation",
            "false de-escalation",
        ],
        "scenario routing expectations",
    )

    # --- Product Owner burden boundary ---------------------------------------------------
    require_all(
        assurance,
        [
            "why more or less verification",
            "time/cost/risk",
            "genuine",
            "tradeoff",
            "one next action",
        ],
        "Product Owner burden boundary",
    )

    print("ASSURANCE ROUTING SELF TEST PASSED")
    print("- formal Engineering scope precondition and responsibility separation")
    print("- boundary regression guard and Engineering-tailoring positive case")
    print("- Universal Assurance Floor non-weakenable; Baseline + additive tailoring")
    print("- Consequence / Reversibility / Specialist Boundary routing inputs")
    print("- AR-01..AR-06; specialist fail-closed; false escalation/de-escalation")
    print("- no fourth Mode/state/engine/score/class/Profile; PO burden boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())