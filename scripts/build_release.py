#!/usr/bin/env python3
"""Build a deterministic public PDC release ZIP and SHA-256 file."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".codex-plugin" / "plugin.json"
INCLUDE = [
    ".codex-plugin",
    "skills",
    "scripts",
    "examples",
    "docs",
    "README.md",
    "START_HERE.md",
    "LICENSE",
    "VERSION",
    "PRIVACY.md",
    "TERMS.md",
    "PUBLIC_RELEASE_SCOPE.md",
    "PUBLIC_VERIFICATION.md",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "ROADMAP.md",
    "RELEASING.md",
]
EXCLUDED_NAMES = {".git", ".github", "__pycache__", ".pytest_cache", ".venv", "venv", "dist"}
FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def plugin_version() -> str:
    payload = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("plugin.json is missing a valid version")
    return version


def should_include(path: Path) -> bool:
    return not any(part in EXCLUDED_NAMES for part in path.parts) and path.suffix != ".pyc"


def iter_files() -> list[Path]:
    result: list[Path] = []
    for item in INCLUDE:
        path = ROOT / item
        if not path.exists():
            raise ValueError(f"required release path is missing: {item}")
        if path.is_file():
            result.append(path)
        else:
            result.extend(p for p in path.rglob("*") if p.is_file() and should_include(p.relative_to(ROOT)))
    return sorted(set(result), key=lambda p: p.as_posix())


def write_zip(destination: Path, version: str) -> None:
    prefix = f"pdc-{version}"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in iter_files():
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", help="Expected version; must match plugin.json")
    p.add_argument("--output-dir", default="dist")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        version = plugin_version()
        if args.version and args.version != version:
            raise ValueError(f"tag/version mismatch: expected {args.version}, plugin.json has {version}")
        output = (ROOT / args.output_dir).resolve()
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        archive = output / f"pdc-{version}.zip"
        write_zip(archive, version)
        digest = sha256(archive)
        checksum = output / f"pdc-{version}.zip.sha256"
        checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
        print(archive)
        print(checksum)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"release build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
