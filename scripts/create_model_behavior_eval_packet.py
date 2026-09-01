#!/usr/bin/env python3
"""Create a provider-neutral PDC model-behavior evaluation packet for an exact Git commit.

The generator never calls a model and never emits a behavior verdict. It prepares
content-addressed subject material, separated execution inputs and evaluator rubric,
and a run-record template that can be handed to a fresh external session or used for
a Controller self-check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_model_behavior_eval import (
    CATALOG_REL,
    OPERATING_MODEL_REL,
    OPERATING_MODEL_SHA256,
    SKILL_REL,
    ValidationError,
    canonical_sha256,
    validate_catalog_data,
)

RUN_TEMPLATE_REL = Path("product-development-controller/assets/evals/model-behavior-run.template.json")


def run_git(root: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args], cwd=str(root),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=text, check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise ValidationError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def git_bytes(root: Path, commit: str, path: Path) -> bytes:
    return run_git(root, "show", f"{commit}:{path.as_posix()}", text=False)  # type: ignore[return-value]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repository_identity(root: Path) -> str:
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], cwd=str(root),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        value = result.stdout.strip()
        candidate = Path(value)
        if candidate.is_absolute():
            return f"local:{candidate.resolve()}"
        return value
    return f"local:{root.resolve()}"


def ensure_output_dir(output: Path) -> None:
    if output.exists():
        if not output.is_dir():
            raise ValidationError(f"output exists and is not a directory: {output}")
        if any(output.iterdir()):
            raise ValidationError(f"output directory must be empty: {output}")
    else:
        output.mkdir(parents=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Git repository root")
    parser.add_argument("--ref", required=True, help="Exact commit or ref resolving to a commit")
    parser.add_argument("--output", type=Path, required=True, help="Empty output directory")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--profile", choices=["full-v1", "operating-model-v1", "stable-v4.2"])
    group.add_argument("--scenario", action="append", dest="scenarios", help="Scenario ID for targeted packet; repeatable")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    output = args.output.resolve()
    try:
        top = Path(str(run_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        if top != root:
            raise ValidationError(f"--root must be the Git toplevel: expected {top}")
        commit = str(run_git(root, "rev-parse", "--verify", f"{args.ref}^{{commit}}")).strip()
        if len(commit) != 40:
            raise ValidationError("resolved commit is not a full 40-character SHA")

        skill_bytes = git_bytes(root, commit, SKILL_REL)
        operating_bytes = git_bytes(root, commit, OPERATING_MODEL_REL)
        catalog_bytes = git_bytes(root, commit, CATALOG_REL)
        template_bytes = git_bytes(root, commit, RUN_TEMPLATE_REL)
        if sha256(operating_bytes) != OPERATING_MODEL_SHA256:
            raise ValidationError("target commit does not contain frozen Product Operating Model v1")
        try:
            catalog = json.loads(catalog_bytes.decode("utf-8"))
            run_template = json.loads(template_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"target commit contains malformed evaluation JSON: {exc}") from exc
        if not isinstance(catalog, dict) or not isinstance(run_template, dict):
            raise ValidationError("catalog and run template must be JSON objects")
        validate_catalog_data(catalog)
        scenario_by_id = {s["id"]: s for s in catalog["scenarios"]}

        if args.scenarios:
            selected: list[str] = []
            for sid in args.scenarios:
                if sid not in scenario_by_id:
                    raise ValidationError(f"unknown targeted scenario id: {sid}")
                if sid in selected:
                    raise ValidationError(f"duplicate targeted scenario id: {sid}")
                selected.append(sid)
            profile = {"name": "targeted", "kind": "targeted", "scenario_ids": selected}
        else:
            profile_name = args.profile or "full-v1"
            profile_source = catalog["profiles"][profile_name]
            profile = {"name": profile_name, "kind": "full", "scenario_ids": list(profile_source["scenario_ids"])}

        subject = {
            "repository_identity": repository_identity(root),
            "commit_sha": commit,
            "skill_path": SKILL_REL.as_posix(),
            "skill_sha256": sha256(skill_bytes),
            "operating_model_path": OPERATING_MODEL_REL.as_posix(),
            "operating_model_sha256": sha256(operating_bytes),
            "catalog_path": CATALOG_REL.as_posix(),
            "catalog_sha256": sha256(catalog_bytes),
        }
        packet_id = canonical_sha256({"subject": subject, "profile": profile})
        ensure_output_dir(output)

        (output / "subject").mkdir(parents=True, exist_ok=True)
        (output / "catalog").mkdir(parents=True, exist_ok=True)
        (output / "execution").mkdir(parents=True, exist_ok=True)
        (output / "evaluator").mkdir(parents=True, exist_ok=True)
        (output / "subject/SKILL.md").write_bytes(skill_bytes)
        (output / "subject/product-operating-model.v1.md").write_bytes(operating_bytes)
        (output / "catalog/model-behavior-scenarios.v1.json").write_bytes(catalog_bytes)

        execution_items = []
        evaluator_items = []
        for sid in profile["scenario_ids"]:
            scenario = scenario_by_id[sid]
            execution_items.append({
                "id": scenario["id"],
                "suite": scenario["suite"],
                "title": scenario["title"],
                "input_setup": scenario["input_setup"],
                "source_reference": scenario["source_reference"],
            })
            evaluator_items.append({
                "id": scenario["id"],
                "suite": scenario["suite"],
                "title": scenario["title"],
                "expected_behavior": scenario["expected_behavior"],
                "failure_condition": scenario["failure_condition"],
                "evaluator_checklist": scenario["evaluator_checklist"],
                "source_reference": scenario["source_reference"],
            })
        write_json(output / "execution/scenario-inputs.json", {
            "schema_version": 1,
            "packet_id": packet_id,
            "subject_commit_sha": commit,
            "profile": profile,
            "instructions": [
                "Execute only the listed scenario inputs against the bound subject.",
                "Do not inspect evaluator/evaluation-rubric.json before producing the scenario response when blind execution is required.",
                "Store one transcript per scenario for later evaluation and hashing.",
            ],
            "scenarios": execution_items,
        })
        write_json(output / "evaluator/evaluation-rubric.json", {
            "schema_version": 1,
            "packet_id": packet_id,
            "subject_commit_sha": commit,
            "profile": profile,
            "baseline_rule": "Judge against this frozen rubric. Suggestions belong in suggested_delta and never rewrite the current verdict or catalog.",
            "scenarios": evaluator_items,
        })

        run_record = run_template
        run_record["packet"] = {"packet_id": packet_id, "catalog_sha256": subject["catalog_sha256"]}
        run_record["subject"] = {
            "repository_identity": subject["repository_identity"],
            "commit_sha": subject["commit_sha"],
            "skill_path": subject["skill_path"],
            "skill_sha256": subject["skill_sha256"],
            "operating_model_sha256": subject["operating_model_sha256"],
        }
        run_record["profile"] = profile
        run_record["declared_status"] = "EVIDENCE_MISSING"
        run_record["results"] = [
            {
                "scenario_id": sid,
                "transcript_path": None,
                "transcript_sha256": None,
                "verdict": "EVIDENCE_MISSING",
                "evaluator_evidence": [],
                "missing_reason": "Scenario has not been executed yet.",
                "suggested_delta": None,
            }
            for sid in profile["scenario_ids"]
        ]
        write_json(output / "run-template.json", run_record)

        (output / "README.md").write_text(
            "# PDC Model Behavior Evaluation Packet\n\n"
            f"Packet ID: `{packet_id}`\n\n"
            f"Subject commit: `{commit}`\n\n"
            f"Profile: `{profile['name']}` ({len(profile['scenario_ids'])} scenarios)\n\n"
            "This packet was generated locally from an exact Git commit. Generation did **not** execute a model, evaluate a response, or perform independent review.\n\n"
            "## Execute\n\n"
            "Give the tested Controller the bound `subject/` material plus `execution/scenario-inputs.json`. Store transcripts outside this packet or in a copied working directory. For blind execution, do not expose `evaluator/` until responses are captured.\n\n"
            "## Evaluate\n\n"
            "Use `evaluator/evaluation-rubric.json` after execution. Fill a copy of `run-template.json`, hash each transcript, and validate it with `validate_model_behavior_eval.py run`.\n\n"
            "`controller_self_check` is useful evidence but is not independent review. If a fresh external session/agent is used, declare `external_fresh_session_attested` and provide the required attestation metadata.\n",
            encoding="utf-8",
        )
        (output / "evaluator/README.md").write_text(
            "# Evaluator Instructions\n\n"
            "Judge each captured transcript against the frozen rubric in this directory. Record PASS, FAIL, or EVIDENCE_MISSING with concrete transcript evidence.\n\n"
            "Do not edit the catalog or expected behavior while scoring. A proposed better rule is a future Baseline + Delta candidate and belongs only in `suggested_delta`.\n\n"
            "The validator checks structure, hashes, coverage, subject binding, and assurance declarations. It does not semantically judge prose and does not cryptographically prove session independence.\n",
            encoding="utf-8",
        )

        file_paths = [
            "README.md",
            "subject/SKILL.md",
            "subject/product-operating-model.v1.md",
            "catalog/model-behavior-scenarios.v1.json",
            "execution/scenario-inputs.json",
            "evaluator/evaluation-rubric.json",
            "evaluator/README.md",
            "run-template.json",
        ]
        files = {rel: sha256((output / rel).read_bytes()) for rel in file_paths}
        manifest = {
            "schema_version": 1,
            "packet_version": 1,
            "packet_id": packet_id,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator": "PDC-4.3-model-behavior-eval",
            "claims": {"model_executed": False, "model_evaluated": False, "independent_review_performed": False},
            "subject": subject,
            "profile": profile,
            "files": files,
        }
        write_json(output / "manifest.json", manifest)
        checksum_paths = ["manifest.json", *file_paths]
        checksum_lines = [f"{sha256((output / rel).read_bytes())}  {rel}" for rel in sorted(checksum_paths)]
        (output / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        print(f"EVALUATION PACKET CREATED packet_id={packet_id} commit={commit} profile={profile['name']} scenarios={len(profile['scenario_ids'])}")
        return 0
    except ValidationError as exc:
        print(f"EVALUATION PACKET ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
