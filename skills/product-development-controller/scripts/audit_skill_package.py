#!/usr/bin/env python3
"""Audit the curated standalone public Skill distribution before packaging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
LEGACY_FILES = {
    "assets/change-templates/task-contract.yaml",
    "assets/change-templates/review-report.yaml",
    "assets/change-templates/acceptance-record.yaml",
    "assets/change-templates/claude-code-prompt.md",
    "assets/project-skeleton/project-state.yaml",
}
EXPECTED_CHANGE_TEMPLATES = {
    "workflow-state.json", "task-contract.draft.json", "product-spec.md", "engineering-plan.md",
    "test-plan.md", "coding-agent-prompt.md", "implementation-report.md", "review-report.json",
    "acceptance-record.json", "integration-record.json",
}
EXPECTED_PROJECT_TEMPLATES = {
    "project-state.json", "project-facts.md", "codebase-facts.md", "roadmap.md", "backlog.md",
}
EXPECTED_PUBLIC_CAPABILITY_FILES = {
    "assets/evals/model-behavior-scenarios.v1.json",
    "assets/evals/model-behavior-run.template.json",
    "assets/evals/global-outcome-control-scenarios.v1.md",
    "references/model-behavior-evaluation.md",
    "references/global-outcome-control.md",
    "scripts/create_model_behavior_eval_packet.py",
    "scripts/validate_model_behavior_eval.py",
    "references/mode-classification-and-control-card.md",
    "references/product-experiment-workflow.md",
    "references/strategic-workpath.md",
    "references/decision-authority.md",
    "references/review-assurance-routing.md",
    "references/handoff-interface.md",
    "references/decision-readiness-routing.md",
    "references/outcome-directed-explore.md",
    "scripts/behavior_evidence_impact.py",
    "references/product-owner-interface.md",
}
EXPECTED_RETAINED_SELF_TESTS = {
    "architecture_v2_control_plane_self_test.py",
    "assurance_routing_self_test.py",
    "authority_projection_coherence_self_test.py",
    "integration_closure_recovery_self_test.py",
    "integration_runner_self_test.py",
    "multi_change_self_test.py",
    "owner_action_activation_self_test.py",
    "reconcile_project_state_self_test.py",
    "verify_authority_reconciliation_self_test.py",
    "workpath_continuity_self_test.py",
    "workpath_publish_recovery_self_test.py",
}
EXCLUDED_PRIVATE_REGRESSION_HARNESSES = {
    "scripts/behavior_evidence_impact_self_test.py",
    "scripts/decision_readiness_self_test.py",
    "scripts/fast_preview_self_test.py",
    "scripts/mode_control_card_self_test.py",
    "scripts/model_behavior_eval_self_test.py",
    "scripts/outcome_directed_explore_self_test.py",
    "scripts/owner_interface_session_self_test.py",
    "scripts/portable_review_durability_self_test.py",
    "scripts/preview_experiment_self_test.py",
    "scripts/review_checks_self_test.py",
    "scripts/stop_scope_self_test.py",
    "scripts/thin_router_self_test.py",
    "scripts/self_test.py",
}


def main() -> int:
    errors: list[str] = []
    if (SKILL_ROOT / ".ai-product").exists():
        errors.append("private project state present: .ai-product")
    if (SKILL_ROOT / "scripts" / "h04_cost_value_measure.py").exists():
        errors.append("private-only measurement script present: scripts/h04_cost_value_measure.py")
    for path in sorted((SKILL_ROOT / "references").glob("quality-upgrade-*.md")):
        errors.append(
            "private package-history note present: "
            + path.relative_to(SKILL_ROOT).as_posix()
        )
    for path in sorted(SKILL_ROOT.iterdir()):
        name = path.name.casefold()
        if path.is_file() and (name == "license" or name.startswith("license.")):
            errors.append(f"license file present: {path.name}")
    for relative in sorted(EXCLUDED_PRIVATE_REGRESSION_HARNESSES):
        if (SKILL_ROOT / relative).exists():
            errors.append(f"private regression harness present: {relative}")
    for path in SKILL_ROOT.rglob("*"):
        relative = path.relative_to(SKILL_ROOT).as_posix()
        if path.is_dir() and path.name == "__pycache__":
            errors.append(f"cache directory present: {relative}")
        if path.is_file() and path.suffix == ".pyc":
            errors.append(f"compiled Python file present: {relative}")
        if relative in LEGACY_FILES:
            errors.append(f"legacy file present: {relative}")
    actual_change = {p.name for p in (SKILL_ROOT / "assets" / "change-templates").iterdir() if p.is_file()}
    actual_project = {p.name for p in (SKILL_ROOT / "assets" / "project-skeleton").iterdir() if p.is_file()}
    if actual_change != EXPECTED_CHANGE_TEMPLATES:
        errors.append(
            "change template whitelist mismatch: "
            f"missing={sorted(EXPECTED_CHANGE_TEMPLATES-actual_change)} extra={sorted(actual_change-EXPECTED_CHANGE_TEMPLATES)}"
        )
    if actual_project != EXPECTED_PROJECT_TEMPLATES:
        errors.append(
            "project template whitelist mismatch: "
            f"missing={sorted(EXPECTED_PROJECT_TEMPLATES-actual_project)} extra={sorted(actual_project-EXPECTED_PROJECT_TEMPLATES)}"
        )
    for relative in sorted(EXPECTED_PUBLIC_CAPABILITY_FILES):
        if not (SKILL_ROOT / relative).is_file():
            errors.append(f"required public capability file missing: {relative}")
    actual_self_tests = {
        path.name for path in (SKILL_ROOT / "scripts").glob("*_self_test.py") if path.is_file()
    }
    if actual_self_tests != EXPECTED_RETAINED_SELF_TESTS:
        errors.append(
            "retained public self-test set mismatch: "
            f"missing={sorted(EXPECTED_RETAINED_SELF_TESTS-actual_self_tests)} "
            f"extra={sorted(actual_self_tests-EXPECTED_RETAINED_SELF_TESTS)}"
        )
    catalog_path = SKILL_ROOT / "assets/evals/model-behavior-scenarios.v1.json"
    run_template_path = SKILL_ROOT / "assets/evals/model-behavior-run.template.json"
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            scenario_ids = [item.get("id") for item in catalog.get("scenarios", []) if isinstance(item, dict)]
            expected_ids = [f"G-{i:02d}" for i in range(1, 20)] + [f"S-{i:02d}" for i in range(1, 25)]
            if catalog.get("schema_version") != 1 or catalog.get("catalog_version") != 1:
                errors.append("evaluation catalog schema/version mismatch")
            if catalog.get("operating_model", {}).get("sha256") != "60657356693d610ede67a12aa8bc564c5791338ca23fa1474d22a02dc5aba82a":
                errors.append("evaluation catalog operating-model digest mismatch")
            if scenario_ids != expected_ids:
                errors.append("evaluation catalog scenario coverage/order mismatch")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"evaluation catalog malformed: {exc}")
    if run_template_path.is_file():
        try:
            template = json.loads(run_template_path.read_text(encoding="utf-8"))
            if template.get("schema_version") != 1 or template.get("assurance", {}).get("type") != "controller_self_check":
                errors.append("evaluation run template schema/default assurance mismatch")
            if template.get("assurance", {}).get("independent_review") is not False:
                errors.append("evaluation run template falsely claims independent review")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"evaluation run template malformed: {exc}")
    if errors:
        print("PUBLIC PACKAGE AUDIT FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PUBLIC PACKAGE AUDIT PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
