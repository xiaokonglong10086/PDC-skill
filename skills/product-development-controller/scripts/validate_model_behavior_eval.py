#!/usr/bin/env python3
"""Validate PDC model-behavior catalogs, packets, and run records.

This validator is deliberately provider-neutral. It validates objective structure,
content bindings, coverage, hashes, and assurance declarations. It does not claim
to semantically judge model transcripts or prove that two sessions are independent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

OPERATING_MODEL_SHA256 = "60657356693d610ede67a12aa8bc564c5791338ca23fa1474d22a02dc5aba82a"
CATALOG_ID = "pdc-model-behavior-scenarios-v1"
CATALOG_REL = Path("product-development-controller/assets/evals/model-behavior-scenarios.v1.json")
OPERATING_MODEL_REL = Path(".ai-product/operating-model/product-operating-model.v1.md")
GOLDEN_REL = Path(".ai-product/operating-model/golden-behavior-scenarios.v1.md")
STABLE_REL = Path("product-development-controller/references/evaluation-scenarios.md")
SKILL_REL = Path("product-development-controller/SKILL.md")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"JSON root must be an object: {path}")
    return data


def require_keys(obj: dict[str, Any], required: set[str], allowed: set[str], where: str) -> None:
    missing = required - set(obj)
    extra = set(obj) - allowed
    if missing:
        raise ValidationError(f"{where} missing keys: {sorted(missing)}")
    if extra:
        raise ValidationError(f"{where} has unsupported keys: {sorted(extra)}")


def require_nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{where} must be a non-empty string")
    return value


def require_digest(value: Any, where: str, pattern: re.Pattern[str] = HEX64) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValidationError(f"{where} must be a lowercase hexadecimal digest")
    return value


def safe_relative_path(value: Any, where: str) -> Path:
    text = require_nonempty_string(value, where)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"{where} must be a safe relative path")
    return path


def parse_golden_source(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(r"^## (G-\d{2}) (.+?)\n(.*?)(?=^## G-\d{2} |\Z)", re.M | re.S)
    result: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        sid, title, body = match.group(1), match.group(2).strip(), match.group(3).strip()
        if "\nExpected:" not in body:
            raise ValidationError(f"golden source {sid} has no Expected section")
        setup, expected = body.rsplit("\nExpected:", 1)
        result.append({"id": sid, "title": title, "input": setup.strip(), "expected": expected.strip()})
    return result


def parse_stable_source(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(r"^## (\d+)\. (.+?)\n(.*?)(?=^## \d+\. |\Z)", re.M | re.S)
    result: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        number, title, body = int(match.group(1)), match.group(2).strip(), match.group(3).strip()
        source_input: str | None = None
        expected: str | None = None
        for paragraph in re.split(r"\n\s*\n", body):
            paragraph = paragraph.strip()
            if paragraph.startswith("Input:"):
                source_input = paragraph[len("Input:"):].strip()
            elif paragraph.startswith("Expected:"):
                expected = paragraph[len("Expected:"):].strip()
        if expected is None:
            raise ValidationError(f"stable source scenario {number} has no Expected section")
        result.append({"id": f"S-{number:02d}", "title": title, "input": source_input, "expected": expected})
    return result


def _validate_scenario_common(scenario: dict[str, Any], where: str) -> None:
    required = {
        "id", "suite", "title", "input_setup", "expected_behavior", "failure_condition",
        "evaluator_checklist", "source_reference",
    }
    require_keys(scenario, required, required, where)
    require_nonempty_string(scenario["id"], f"{where}.id")
    if scenario["suite"] not in {"operating-model-v1", "stable-v4.2"}:
        raise ValidationError(f"{where}.suite is unsupported")
    require_nonempty_string(scenario["title"], f"{where}.title")
    input_setup = scenario["input_setup"]
    if not isinstance(input_setup, dict):
        raise ValidationError(f"{where}.input_setup must be an object")
    require_keys(input_setup, {"source_provided", "text"}, {"source_provided", "text"}, f"{where}.input_setup")
    if not isinstance(input_setup["source_provided"], bool):
        raise ValidationError(f"{where}.input_setup.source_provided must be boolean")
    if input_setup["source_provided"]:
        require_nonempty_string(input_setup["text"], f"{where}.input_setup.text")
    elif input_setup["text"] is not None:
        raise ValidationError(f"{where}.input_setup.text must be null when source_provided is false")
    require_nonempty_string(scenario["expected_behavior"], f"{where}.expected_behavior")
    require_nonempty_string(scenario["failure_condition"], f"{where}.failure_condition")
    checklist = scenario["evaluator_checklist"]
    if not isinstance(checklist, list) or not checklist or any(not isinstance(x, str) or not x.strip() for x in checklist):
        raise ValidationError(f"{where}.evaluator_checklist must contain non-empty strings")
    require_nonempty_string(scenario["source_reference"], f"{where}.source_reference")


def validate_catalog_data(catalog: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    required = {"schema_version", "catalog_version", "catalog_id", "description", "operating_model", "source_suites", "profiles", "scenarios"}
    require_keys(catalog, required, required, "catalog")
    if catalog["schema_version"] != 1 or catalog["catalog_version"] != 1 or catalog["catalog_id"] != CATALOG_ID:
        raise ValidationError("unsupported catalog identity/version")
    require_nonempty_string(catalog["description"], "catalog.description")

    operating = catalog["operating_model"]
    if not isinstance(operating, dict):
        raise ValidationError("catalog.operating_model must be an object")
    require_keys(operating, {"version", "path", "sha256"}, {"version", "path", "sha256"}, "catalog.operating_model")
    if operating["version"] != 1 or operating["path"] != OPERATING_MODEL_REL.as_posix() or operating["sha256"] != OPERATING_MODEL_SHA256:
        raise ValidationError("catalog operating-model binding does not match frozen Product Operating Model v1")

    scenarios = catalog["scenarios"]
    if not isinstance(scenarios, list):
        raise ValidationError("catalog.scenarios must be an array")
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValidationError(f"catalog.scenarios[{idx}] must be an object")
        _validate_scenario_common(scenario, f"catalog.scenarios[{idx}]")
        sid = scenario["id"]
        if sid in by_id:
            raise ValidationError(f"duplicate scenario id: {sid}")
        ids.append(sid)
        by_id[sid] = scenario

    golden_ids = [f"G-{i:02d}" for i in range(1, 20)]
    stable_ids = [f"S-{i:02d}" for i in range(1, 25)]
    expected_ids = golden_ids + stable_ids
    if ids != expected_ids:
        raise ValidationError(f"catalog scenario order/coverage mismatch: expected {expected_ids}, got {ids}")
    for sid in golden_ids:
        if by_id[sid]["suite"] != "operating-model-v1":
            raise ValidationError(f"{sid} is not in operating-model-v1")
    for sid in stable_ids:
        if by_id[sid]["suite"] != "stable-v4.2":
            raise ValidationError(f"{sid} is not in stable-v4.2")

    suites = catalog["source_suites"]
    if not isinstance(suites, list) or len(suites) != 2:
        raise ValidationError("catalog.source_suites must contain exactly two suites")
    suite_by_id = {s.get("id"): s for s in suites if isinstance(s, dict)}
    if set(suite_by_id) != {"operating-model-v1", "stable-v4.2"}:
        raise ValidationError("catalog.source_suites ids are invalid")
    golden_suite = suite_by_id["operating-model-v1"]
    require_keys(golden_suite, {"id", "source_path", "source_sha256", "scenario_ids"}, {"id", "source_path", "source_sha256", "scenario_ids"}, "operating-model-v1 suite")
    if golden_suite["source_path"] != GOLDEN_REL.as_posix() or golden_suite["scenario_ids"] != golden_ids:
        raise ValidationError("operating-model-v1 suite binding mismatch")
    require_digest(golden_suite["source_sha256"], "operating-model-v1 source_sha256")
    stable_suite = suite_by_id["stable-v4.2"]
    require_keys(stable_suite, {"id", "source_path", "stable_tag", "scenario_ids"}, {"id", "source_path", "stable_tag", "scenario_ids"}, "stable-v4.2 suite")
    if stable_suite["source_path"] != STABLE_REL.as_posix() or stable_suite["stable_tag"] != "pdc-v4.2.0" or stable_suite["scenario_ids"] != stable_ids:
        raise ValidationError("stable-v4.2 suite binding mismatch")

    profiles = catalog["profiles"]
    if not isinstance(profiles, dict):
        raise ValidationError("catalog.profiles must be an object")
    expected_profiles = {
        "full-v1": expected_ids,
        "operating-model-v1": golden_ids,
        "stable-v4.2": stable_ids,
    }
    if set(profiles) != set(expected_profiles):
        raise ValidationError("catalog profiles must be exactly full-v1, operating-model-v1, stable-v4.2")
    for name, scenario_ids in expected_profiles.items():
        profile = profiles[name]
        if not isinstance(profile, dict):
            raise ValidationError(f"catalog.profiles.{name} must be an object")
        require_keys(profile, {"kind", "scenario_ids"}, {"kind", "scenario_ids"}, f"catalog.profiles.{name}")
        if profile["kind"] != "full" or profile["scenario_ids"] != scenario_ids:
            raise ValidationError(f"catalog.profiles.{name} coverage mismatch")

    if root is not None:
        operating_path = root / OPERATING_MODEL_REL
        golden_path = root / GOLDEN_REL
        stable_path = root / STABLE_REL
        for path in (operating_path, golden_path, stable_path):
            if not path.is_file():
                raise ValidationError(f"required source file missing: {path}")
        if sha256_file(operating_path) != OPERATING_MODEL_SHA256:
            raise ValidationError("frozen Product Operating Model digest mismatch")
        if sha256_file(golden_path) != golden_suite["source_sha256"]:
            raise ValidationError("golden behavior source digest mismatch")

        golden_source = parse_golden_source(golden_path.read_text(encoding="utf-8"))
        if [x["id"] for x in golden_source] != golden_ids:
            raise ValidationError("golden source must contain G-01 through G-19 exactly once")
        for source in golden_source:
            scenario = by_id[source["id"]]
            if scenario["title"] != source["title"] or scenario["input_setup"] != {"source_provided": True, "text": source["input"]} or scenario["expected_behavior"] != source["expected"]:
                raise ValidationError(f"catalog weakens or changes approved golden scenario {source['id']}")

        stable_source = parse_stable_source(stable_path.read_text(encoding="utf-8"))
        if [x["id"] for x in stable_source] != stable_ids:
            raise ValidationError("stable source must contain 24 scenarios exactly once")
        for source in stable_source:
            scenario = by_id[source["id"]]
            expected_input = {"source_provided": source["input"] is not None, "text": source["input"]}
            if scenario["title"] != source["title"] or scenario["input_setup"] != expected_input or scenario["expected_behavior"] != source["expected"]:
                raise ValidationError(f"catalog weakens or changes stable scenario {source['id']}")

    return {"scenario_count": len(ids), "catalog_content_sha256": canonical_sha256(catalog)}


def parse_checksum_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"cannot read checksum manifest: {exc}") from exc
    for line in lines:
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValidationError(f"invalid SHA256SUMS line: {line!r}")
        digest, rel = match.groups()
        rel_path = safe_relative_path(rel, "SHA256SUMS path")
        key = rel_path.as_posix()
        if key in result:
            raise ValidationError(f"duplicate SHA256SUMS path: {key}")
        result[key] = digest
    return result


def validate_packet_dir(packet_dir: Path) -> dict[str, Any]:
    if not packet_dir.is_dir():
        raise ValidationError(f"packet directory not found: {packet_dir}")
    sums_path = packet_dir / "SHA256SUMS.txt"
    sums = parse_checksum_manifest(sums_path)
    required_files = {
        "README.md",
        "manifest.json",
        "subject/SKILL.md",
        "subject/product-operating-model.v1.md",
        "catalog/model-behavior-scenarios.v1.json",
        "execution/scenario-inputs.json",
        "evaluator/evaluation-rubric.json",
        "evaluator/README.md",
        "run-template.json",
    }
    if set(sums) != required_files:
        raise ValidationError(f"packet checksum file set mismatch: missing={sorted(required_files-set(sums))} extra={sorted(set(sums)-required_files)}")
    for rel, expected in sums.items():
        path = packet_dir / rel
        if not path.is_file() or sha256_file(path) != expected:
            raise ValidationError(f"packet file checksum mismatch: {rel}")

    manifest = read_json(packet_dir / "manifest.json")
    required_manifest = {"schema_version", "packet_version", "packet_id", "generated_at", "generator", "claims", "subject", "profile", "files"}
    require_keys(manifest, required_manifest, required_manifest, "manifest")
    if manifest["schema_version"] != 1 or manifest["packet_version"] != 1 or manifest["generator"] != "PDC-4.3-model-behavior-eval":
        raise ValidationError("unsupported packet manifest version")
    require_digest(manifest["packet_id"], "manifest.packet_id")
    require_nonempty_string(manifest["generated_at"], "manifest.generated_at")
    claims = manifest["claims"]
    if claims != {"model_executed": False, "model_evaluated": False, "independent_review_performed": False}:
        raise ValidationError("packet generation must make no execution/evaluation/independence claim")

    subject = manifest["subject"]
    subject_required = {"repository_identity", "commit_sha", "skill_path", "skill_sha256", "operating_model_path", "operating_model_sha256", "catalog_path", "catalog_sha256"}
    if not isinstance(subject, dict):
        raise ValidationError("manifest.subject must be an object")
    require_keys(subject, subject_required, subject_required, "manifest.subject")
    require_nonempty_string(subject["repository_identity"], "manifest.subject.repository_identity")
    require_digest(subject["commit_sha"], "manifest.subject.commit_sha", HEX40)
    if subject["skill_path"] != SKILL_REL.as_posix() or subject["operating_model_path"] != OPERATING_MODEL_REL.as_posix() or subject["catalog_path"] != CATALOG_REL.as_posix():
        raise ValidationError("packet subject paths are not canonical")
    require_digest(subject["skill_sha256"], "manifest.subject.skill_sha256")
    require_digest(subject["catalog_sha256"], "manifest.subject.catalog_sha256")
    if subject["operating_model_sha256"] != OPERATING_MODEL_SHA256:
        raise ValidationError("packet subject operating-model digest mismatch")
    if sha256_file(packet_dir / "subject/SKILL.md") != subject["skill_sha256"]:
        raise ValidationError("packet Skill content does not match subject digest")
    if sha256_file(packet_dir / "subject/product-operating-model.v1.md") != subject["operating_model_sha256"]:
        raise ValidationError("packet operating model does not match subject digest")
    if sha256_file(packet_dir / "catalog/model-behavior-scenarios.v1.json") != subject["catalog_sha256"]:
        raise ValidationError("packet catalog does not match subject digest")

    catalog = read_json(packet_dir / "catalog/model-behavior-scenarios.v1.json")
    validate_catalog_data(catalog)
    scenario_by_id = {x["id"]: x for x in catalog["scenarios"]}

    profile = manifest["profile"]
    if not isinstance(profile, dict):
        raise ValidationError("manifest.profile must be an object")
    require_keys(profile, {"name", "kind", "scenario_ids"}, {"name", "kind", "scenario_ids"}, "manifest.profile")
    if profile["kind"] not in {"full", "targeted"}:
        raise ValidationError("manifest.profile.kind must be full or targeted")
    ids = profile["scenario_ids"]
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or any(x not in scenario_by_id for x in ids):
        raise ValidationError("manifest.profile.scenario_ids are invalid")
    if profile["kind"] == "full":
        expected = catalog["profiles"].get(profile["name"])
        if not expected or expected["scenario_ids"] != ids:
            raise ValidationError("full packet profile does not match catalog profile")
    elif profile["name"] != "targeted":
        raise ValidationError("targeted packet profile name must be targeted")

    execution = read_json(packet_dir / "execution/scenario-inputs.json")
    evaluator = read_json(packet_dir / "evaluator/evaluation-rubric.json")
    if execution.get("packet_id") != manifest["packet_id"] or evaluator.get("packet_id") != manifest["packet_id"]:
        raise ValidationError("execution/evaluator materials are bound to another packet")
    execution_items = execution.get("scenarios")
    evaluator_items = evaluator.get("scenarios")
    if not isinstance(execution_items, list) or not isinstance(evaluator_items, list):
        raise ValidationError("execution/evaluator scenarios must be arrays")
    if [x.get("id") for x in execution_items if isinstance(x, dict)] != ids or [x.get("id") for x in evaluator_items if isinstance(x, dict)] != ids:
        raise ValidationError("execution/evaluator scenario coverage does not match packet profile")
    forbidden_execution_keys = {"expected_behavior", "failure_condition", "evaluator_checklist"}
    for idx, item in enumerate(execution_items):
        if not isinstance(item, dict) or forbidden_execution_keys & set(item):
            raise ValidationError(f"execution scenario {idx} exposes evaluator expected-behavior material")
    for item in evaluator_items:
        if not isinstance(item, dict):
            raise ValidationError("evaluator scenario must be an object")
        source = scenario_by_id[item.get("id")]
        if item.get("expected_behavior") != source["expected_behavior"] or item.get("failure_condition") != source["failure_condition"] or item.get("evaluator_checklist") != source["evaluator_checklist"]:
            raise ValidationError(f"evaluator rubric drift for {item.get('id')}")

    files = manifest["files"]
    if not isinstance(files, dict) or set(files) != required_files - {"manifest.json"}:
        raise ValidationError("manifest.files does not list the expected packet files")
    for rel, digest in files.items():
        require_digest(digest, f"manifest.files[{rel}]")
        if sha256_file(packet_dir / rel) != digest:
            raise ValidationError(f"manifest file digest mismatch: {rel}")

    expected_packet_id = canonical_sha256({"subject": subject, "profile": profile})
    if manifest["packet_id"] != expected_packet_id:
        raise ValidationError("packet_id does not match subject/profile binding")
    return {"packet_id": manifest["packet_id"], "subject": subject, "profile": profile, "catalog": catalog}


def derive_status(profile_kind: str, required_ids: list[str], result_by_id: dict[str, dict[str, Any]]) -> str:
    if any(sid not in result_by_id for sid in required_ids):
        return "EVIDENCE_MISSING"
    verdicts = [result_by_id[sid]["verdict"] for sid in required_ids]
    if "EVIDENCE_MISSING" in verdicts:
        return "EVIDENCE_MISSING"
    if "FAIL" in verdicts:
        return "FAIL"
    if all(v == "PASS" for v in verdicts):
        return "PASS" if profile_kind == "full" else "PARTIAL"
    raise ValidationError("cannot derive run status")


def validate_run_file(run_path: Path, packet_dir: Path) -> dict[str, Any]:
    packet = validate_packet_dir(packet_dir)
    run = read_json(run_path)
    required = {"schema_version", "run_id", "created_at", "packet", "subject", "profile", "assurance", "declared_status", "results"}
    require_keys(run, required, required, "run")
    if run["schema_version"] != 1:
        raise ValidationError("unsupported run schema_version")
    require_nonempty_string(run["run_id"], "run.run_id")
    require_nonempty_string(run["created_at"], "run.created_at")

    packet_binding = run["packet"]
    if not isinstance(packet_binding, dict):
        raise ValidationError("run.packet must be an object")
    require_keys(packet_binding, {"packet_id", "catalog_sha256"}, {"packet_id", "catalog_sha256"}, "run.packet")
    if packet_binding["packet_id"] != packet["packet_id"] or packet_binding["catalog_sha256"] != packet["subject"]["catalog_sha256"]:
        raise ValidationError("run packet/catalog binding mismatch")

    subject = run["subject"]
    if subject != {
        "repository_identity": packet["subject"]["repository_identity"],
        "commit_sha": packet["subject"]["commit_sha"],
        "skill_path": packet["subject"]["skill_path"],
        "skill_sha256": packet["subject"]["skill_sha256"],
        "operating_model_sha256": packet["subject"]["operating_model_sha256"],
    }:
        raise ValidationError("run subject binding mismatch")

    if run["profile"] != packet["profile"]:
        raise ValidationError("run profile differs from packet profile")
    profile = packet["profile"]
    required_ids = profile["scenario_ids"]

    assurance = run["assurance"]
    if not isinstance(assurance, dict):
        raise ValidationError("run.assurance must be an object")
    assurance_keys = {"type", "independent_review", "execution_context", "evaluation_context", "external_attestation"}
    require_keys(assurance, assurance_keys, assurance_keys, "run.assurance")
    assurance_type = assurance["type"]
    if assurance_type not in {"controller_self_check", "external_fresh_session_attested"}:
        raise ValidationError("unsupported assurance type")
    if not isinstance(assurance["execution_context"], dict) or not isinstance(assurance["evaluation_context"], dict):
        raise ValidationError("execution/evaluation context must be objects")
    exec_ctx = assurance["execution_context"]
    eval_ctx = assurance["evaluation_context"]
    require_keys(exec_ctx, {"executor", "session_id", "fresh_session_declared"}, {"executor", "session_id", "fresh_session_declared"}, "run.assurance.execution_context")
    require_keys(eval_ctx, {"evaluator", "session_id"}, {"evaluator", "session_id"}, "run.assurance.evaluation_context")
    require_nonempty_string(exec_ctx["executor"], "execution_context.executor")
    require_nonempty_string(exec_ctx["session_id"], "execution_context.session_id")
    require_nonempty_string(eval_ctx["evaluator"], "evaluation_context.evaluator")
    require_nonempty_string(eval_ctx["session_id"], "evaluation_context.session_id")
    if not isinstance(exec_ctx["fresh_session_declared"], bool):
        raise ValidationError("execution_context.fresh_session_declared must be boolean")

    if assurance_type == "controller_self_check":
        if assurance["independent_review"] is not False or assurance["external_attestation"] is not None:
            raise ValidationError("controller_self_check cannot claim independent review or external attestation")
    else:
        if assurance["independent_review"] is not True or exec_ctx["fresh_session_declared"] is not True:
            raise ValidationError("external_fresh_session_attested requires independent_review=true and fresh_session_declared=true")
        att = assurance["external_attestation"]
        if not isinstance(att, dict):
            raise ValidationError("external_fresh_session_attested requires external_attestation")
        require_keys(att, {"attested_by", "attested_at", "statement"}, {"attested_by", "attested_at", "statement"}, "external_attestation")
        require_nonempty_string(att["attested_by"], "external_attestation.attested_by")
        require_nonempty_string(att["attested_at"], "external_attestation.attested_at")
        require_nonempty_string(att["statement"], "external_attestation.statement")

    results = run["results"]
    if not isinstance(results, list):
        raise ValidationError("run.results must be an array")
    result_by_id: dict[str, dict[str, Any]] = {}
    transcript_owners: dict[tuple[str, str], list[dict[str, Any]]] = {}
    allowed_result_keys = {"scenario_id", "transcript_path", "transcript_sha256", "verdict", "evaluator_evidence", "missing_reason", "suggested_delta", "transcript_reuse_reason"}
    required_result_keys = allowed_result_keys - {"transcript_reuse_reason"}
    run_dir = run_path.parent
    for idx, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValidationError(f"run.results[{idx}] must be an object")
        require_keys(result, required_result_keys, allowed_result_keys, f"run.results[{idx}]")
        sid = require_nonempty_string(result["scenario_id"], f"run.results[{idx}].scenario_id")
        if sid not in required_ids:
            raise ValidationError(f"result scenario {sid} is not selected by the packet")
        if sid in result_by_id:
            raise ValidationError(f"duplicate result scenario id: {sid}")
        verdict = result["verdict"]
        if verdict not in {"PASS", "FAIL", "EVIDENCE_MISSING"}:
            raise ValidationError(f"unsupported verdict for {sid}")
        evidence = result["evaluator_evidence"]
        if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
            raise ValidationError(f"evaluator_evidence must be an array of non-empty strings for {sid}")
        suggested = result["suggested_delta"]
        if suggested is not None and (not isinstance(suggested, str) or not suggested.strip()):
            raise ValidationError(f"suggested_delta must be null or non-empty string for {sid}")
        if verdict in {"PASS", "FAIL"}:
            transcript_rel = safe_relative_path(result["transcript_path"], f"{sid}.transcript_path")
            digest = require_digest(result["transcript_sha256"], f"{sid}.transcript_sha256")
            transcript = run_dir / transcript_rel
            if not transcript.is_file():
                raise ValidationError(f"transcript missing for {sid}: {transcript_rel}")
            if sha256_file(transcript) != digest:
                raise ValidationError(f"transcript hash mismatch for {sid}")
            if not evidence:
                raise ValidationError(f"PASS/FAIL requires evaluator evidence for {sid}")
            if result["missing_reason"] is not None:
                raise ValidationError(f"PASS/FAIL cannot include missing_reason for {sid}")
            transcript_owners.setdefault((transcript_rel.as_posix(), digest), []).append(result)
        else:
            if result["transcript_path"] is not None or result["transcript_sha256"] is not None:
                if result["transcript_path"] is None or result["transcript_sha256"] is None:
                    raise ValidationError(f"EVIDENCE_MISSING transcript path/hash must both be present or both null for {sid}")
                transcript_rel = safe_relative_path(result["transcript_path"], f"{sid}.transcript_path")
                digest = require_digest(result["transcript_sha256"], f"{sid}.transcript_sha256")
                transcript = run_dir / transcript_rel
                if not transcript.is_file() or sha256_file(transcript) != digest:
                    raise ValidationError(f"present transcript binding is invalid for {sid}")
            require_nonempty_string(result["missing_reason"], f"{sid}.missing_reason")
        result_by_id[sid] = result

    for key, owners in transcript_owners.items():
        if len(owners) > 1:
            if any(not isinstance(item.get("transcript_reuse_reason"), str) or not item["transcript_reuse_reason"].strip() for item in owners):
                raise ValidationError(f"transcript reused across scenarios without explicit reuse reason: {key[0]}")

    derived = derive_status(profile["kind"], required_ids, result_by_id)
    if run["declared_status"] not in {"PASS", "FAIL", "EVIDENCE_MISSING", "PARTIAL"}:
        raise ValidationError("run.declared_status is unsupported")
    if run["declared_status"] != derived:
        raise ValidationError(f"declared_status {run['declared_status']} contradicts derived status {derived}")
    if profile["kind"] == "targeted" and run["declared_status"] == "PASS":
        raise ValidationError("targeted runs cannot claim full PASS")
    return {"status": derived, "assurance": assurance_type, "scenario_count": len(result_by_id), "packet_id": packet["packet_id"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="validate a catalog")
    catalog.add_argument("catalog_path", type=Path)
    catalog.add_argument("--root", type=Path)
    packet = sub.add_parser("packet", help="validate an evaluation packet")
    packet.add_argument("packet_dir", type=Path)
    run = sub.add_parser("run", help="validate a run record against a packet")
    run.add_argument("run_path", type=Path)
    run.add_argument("--packet", dest="packet_dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "catalog":
            catalog = read_json(args.catalog_path)
            summary = validate_catalog_data(catalog, args.root.resolve() if args.root else None)
            print(f"VALID CATALOG scenarios={summary['scenario_count']}")
        elif args.command == "packet":
            summary = validate_packet_dir(args.packet_dir.resolve())
            print(f"VALID PACKET packet_id={summary['packet_id']} profile={summary['profile']['name']}")
        else:
            summary = validate_run_file(args.run_path.resolve(), args.packet_dir.resolve())
            print(f"VALID RUN status={summary['status']} assurance={summary['assurance']} scenarios={summary['scenario_count']}")
        return 0
    except ValidationError as exc:
        print(f"INVALID MODEL BEHAVIOR EVIDENCE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
