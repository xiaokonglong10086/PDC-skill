#!/usr/bin/env python3
"""Focused invariant checks for the frozen GF-M1 Architecture v2 production control plane.

Protects the contract v3 completion boundary deterministically:
exactly five Kernel concepts, exactly three Modes, Builder as the universal
execution abstraction, Strategic Workpath as a reachable Strategy-level
planning projection (never a fourth Mode / sixth Kernel concept / lifecycle
state / second Work engine), future waypoints not automatically becoming
Work, Direct Engineering preserved, Preview never production qualification,
S-17 executable technical handoff reachability, current formal-Engineering
coverage boundary, and the unchanged strict Software/PDC machinery.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
SKILL = SKILL_ROOT / "SKILL.md"
KERNEL = SKILL_ROOT / "references" / "architecture-v2-kernel.md"
WORKPATH = SKILL_ROOT / "references" / "strategic-workpath.md"
CAPABILITY = SKILL_ROOT / "references" / "capability-and-assurance.md"
PROFILE_ROUTING = SKILL_ROOT / "references" / "development-profile-routing.md"
PROFILE_SOFTWARE = SKILL_ROOT / "references" / "profile-software-pdc.md"
OWNER_INTERFACE = SKILL_ROOT / "references" / "product-owner-interface.md"
HANDOFF = SKILL_ROOT / "references" / "handoff-interface.md"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"required Architecture v2 control-plane file missing: {path.name}")
    return path.read_text(encoding="utf-8")


def require_all(haystack: str, needles: list[str], context: str) -> None:
    missing = [needle for needle in needles if needle not in haystack]
    if missing:
        raise AssertionError(f"{context} missing required markers: {missing}")


def require_absent(haystack: str, needles: list[str], context: str) -> None:
    present = [needle for needle in needles if needle in haystack]
    if present:
        raise AssertionError(f"{context} contains forbidden markers: {present}")


def headings(markdown: str, level: int) -> list[str]:
    pattern = re.compile(rf"^{'#' * level}\s+(.+?)\s*$", re.MULTILINE)
    return [match.strip() for match in pattern.findall(markdown)]


def section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^(#{{2,3}})\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        raise AssertionError(f"missing section: {heading}")
    level = len(match.group(1))
    rest = markdown[match.end():]
    boundary = re.compile(rf"^#{{{level - 1 if level > 2 else 1},{level}}}\s", re.MULTILINE)
    nxt = boundary.search(rest)
    return rest[: nxt.start()] if nxt else rest


def main() -> int:
    parser = argparse.ArgumentParser(description="GF-M1 Architecture v2 control-plane invariant checks.")
    parser.add_argument("--smoke", action="store_true", help="Accepted for uniform frozen-test invocation; same checks run.")
    parser.parse_args()

    skill = read(SKILL)
    kernel = read(KERNEL)
    workpath = read(WORKPATH)
    capability = read(CAPABILITY)
    profile_routing = read(PROFILE_ROUTING)
    profile_software = read(PROFILE_SOFTWARE)
    owner_interface = read(OWNER_INTERFACE)
    handoff = read(HANDOFF)

    # --- Exactly five Kernel concepts, no sixth ---------------------------------
    require_all(
        kernel,
        [
            "## Five stable kernel concepts",
            "### 1. Outcome",
            "### 2. Work",
            "### 3. Mode",
            "### 4. Control Decision",
            "### 5. Evidence & Authority",
        ],
        "kernel concepts",
    )
    kernel_concept_headings = [h for h in headings(kernel, 3) if re.match(r"^\d+\.\s", h)]
    assert len(kernel_concept_headings) == 5, f"kernel must define exactly five concepts: {kernel_concept_headings}"
    require_all(
        skill,
        [
            "## Five kernel concepts",
            "**Outcome**",
            "**Work**",
            "**Mode**",
            "**Control Decision**",
            "**Evidence & Authority**",
        ],
        "SKILL kernel concepts",
    )

    # --- Exactly three Modes ------------------------------------------------------
    require_all(
        kernel,
        [
            "- **Explore** — reduce material direction/domain/product uncertainty fastest.",
            "- **Preview** — obtain credible reality evidence about a defined uncertainty with the smallest credible loop.",
            "- **Engineering** — reliably construct, repair, maintain, verify, or deliver sufficiently understood/approved behavior.",
            "Do not add a fourth mode",
        ],
        "kernel modes",
    )
    skill_mode_section = section(skill, "Mode routing")
    for mode_heading in ("### Explore", "### Preview", "### Engineering"):
        assert mode_heading in skill_mode_section, f"SKILL Mode routing missing {mode_heading}"
    skill_mode_headings = [h for h in headings(skill_mode_section, 3)]
    assert skill_mode_headings == ["Explore", "Preview", "Engineering"], skill_mode_headings
    require_all(skill, ["Classify Mode from the **current optimization objective**"], "SKILL mode classification")

    # --- Builder universal / Coding Agent profile Builder --------------------------
    require_all(
        skill,
        [
            "**Builder** — executes bounded work",
            "A Coding Agent is one Builder type for the current repository-backed Software/PDC Engineering Profile.",
            "cannot silently redefine product intent",
        ],
        "SKILL Builder boundary",
    )

    # --- Strategic Workpath reachable as Strategy, not Mode/Kernel/state/engine ----
    require_all(skill, ["references/strategic-workpath.md"], "SKILL Strategic Workpath reachability")
    require_all(
        workpath,
        [
            "Strategy",
            "Work-control planning projection",
            "Outcome",
            "waypoint",
            "current position",
            "Ordering rationale",
            "advancement",
            "provisional",
        ],
        "Strategic Workpath route shape",
    )
    require_all(
        workpath,
        [
            "advance the current credible Workpath",
            "decisive evidence",
            "blocker",
            "replan",
        ],
        "Strategic Workpath next-action discipline",
    )
    require_all(
        workpath,
        [
            "current path",
            "known later",
            "route revision",
            "separate Work",
            "does not serve",
        ],
        "Strategic Workpath five-way idea/evidence classification",
    )
    require_all(
        workpath,
        [
            "local-optimum",
            "path-deviation",
            "sunk-cost",
            "gating risk",
        ],
        "Strategic Workpath local-optimum/path-deviation detection",
    )
    require_all(
        workpath,
        [
            "Reuse",
            "Adapt",
            "Innovate",
            "evidence",
        ],
        "Strategic Workpath professional-practice-as-evidence",
    )
    require_all(
        workpath,
        [
            "overall route",
            "why this now",
            "one next action",
        ],
        "Strategic Workpath Product Owner route disclosure",
    )

    # Anti-inflation: Workpath is not a Mode, Kernel concept, lifecycle state, or engine.
    require_all(
        workpath,
        [
            "not a Kernel concept",
            "not a Mode",
            "not a lifecycle state",
            "not a workflow engine",
            "not a scheduler",
            "not a dependency graph",
            "not a Work state machine",
            "do not automatically become Work",
        ],
        "Strategic Workpath anti-inflation boundary",
    )
    require_absent(
        workpath,
        [
            "fourth Mode",
            "Planning Mode",
            "sixth Kernel concept",
            "sixth kernel concept",
            "second Work engine",
            "second Work state machine",
            "workpath state machine",
        ],
        "Strategic Workpath must not affirmatively introduce forbidden mechanisms",
    )
    # The kernel concept list and SKILL mode list must remain exactly five/three even with Workpath present.
    assert len(kernel_concept_headings) == 5
    assert skill_mode_headings == ["Explore", "Preview", "Engineering"]

    # --- Direct Engineering preserved / no forced stage order ----------------------
    require_all(
        skill,
        [
            "Use **Engineering** when the behavior is sufficiently understood/approved",
            "do not require Preview before",
        ],
        "Direct Engineering preserved",
    )
    require_absent(skill, ["must pass through Preview before Engineering"], "no forced Preview gate")

    # --- Preview evidence boundary --------------------------------------------------
    require_all(
        skill,
        [
            "do not mistake Preview success for production qualification",
            "Preview evidence may support an Engineering decision",
            "frozen Engineering boundary",
        ],
        "Preview/Engineering boundary",
    )

    # --- S-17 executable technical handoff reachable -------------------------------
    require_all(skill, ["references/capability-and-assurance.md"], "SKILL capability-assurance reachability")
    require_all(
        capability,
        [
            "executable technical handoff",
            "bounded objective",
            "artifact",
            "frozen",
            "requested action",
            "expected returned evidence",
            "stop conditions",
            "unverified",
            "direct delegation",
            "Human Courier",
        ],
        "S-17 executable handoff authority",
    )
    require_all(
        capability,
        [
            "cannot fabricate",
        ],
        "S-17 no fabricated completion",
    )

    # --- Current formal Engineering coverage boundary ------------------------------
    require_all(
        skill,
        [
            "## Current Development Profile coverage",
            "The current fully implemented strict formal Engineering Profile is repository-backed **Software/PDC**",
            "Do **not** claim that strict formal Engineering Profiles for those deliverables already exist",
        ],
        "current coverage boundary",
    )

    # --- Software/PDC strict machinery not replaced --------------------------------
    require_all(
        profile_software,
        [
            "scripts/validate_task_contract.py",
            "scripts/freeze_contract.py",
            "scripts/capture_implementation_snapshot.py",
            "scripts/run_review_checks.py",
            "## Exact-target Controller verification",
            "cannot substitute",
            "## Frozen completion boundary",
        ],
        "Software/PDC strict machinery preserved",
    )
    require_all(
        profile_routing,
        [
            "the only fully implemented strict formal Engineering Profile",
            "Fail closed on the unsupported claim",
        ],
        "profile routing boundary",
    )

    # --- One Focus / one next action / no parallel advancing Work ------------------
    require_all(
        skill,
        [
            "keep exactly one advancing Work Focus",
            "identify exactly one required next action",
        ],
        "one Focus / one next action",
    )

    # --- Owner interface / continuity still reachable -------------------------------
    require_all(
        skill,
        [
            "references/product-owner-interface.md",
            "references/handoff-interface.md",
        ],
        "owner interface and continuity reachability",
    )
    require_all(owner_interface, ["least unnecessary cognitive and technical burden"], "owner collaboration outcome")
    require_all(handoff, ["index, not"], "continuity capsule is an index")

    print("ARCHITECTURE V2 CONTROL PLANE SELF TEST PASSED")
    print("- exactly five Kernel concepts and exactly three Modes")
    print("- Builder universal with Coding Agent as the current Software/PDC Builder")
    print("- Strategic Workpath reachable as Strategy, never Mode/Kernel/state/engine")
    print("- future waypoints do not automatically become Work; one advancing Focus")
    print("- Direct Engineering preserved; Preview never production qualification")
    print("- S-17 executable technical handoff reachable without PO technical judgment")
    print("- current coverage boundary and strict Software/PDC machinery preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
