#!/usr/bin/env python3
"""Small repository validation for exported Codex skills."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


NAME_RE = re.compile(r"^[a-z0-9-]{1,63}$")


def _frontmatter(skill_md: Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        _, raw, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter must be closed with ---") from exc
    if not body.strip():
        raise ValueError("SKILL.md body must not be empty")

    values: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    if not skill_dir.is_dir():
        return [f"Skill directory not found: {skill_dir}"]

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"Missing {skill_md}"]

    try:
        meta = _frontmatter(skill_md)
    except ValueError as exc:
        errors.append(str(exc))
        meta = {}

    name = meta.get("name", "")
    if not NAME_RE.fullmatch(name):
        errors.append("Frontmatter name must be lowercase letters, digits, and hyphens")
    if name and skill_dir.name != name:
        errors.append(f"Skill directory name must match frontmatter name: {name}")
    if not meta.get("description"):
        errors.append("Frontmatter description is required")

    for path in skill_dir.rglob("*"):
        if "__pycache__" in path.parts:
            errors.append(f"Remove Python cache path: {path}")
        if path.suffix == ".pyc":
            errors.append(f"Remove Python bytecode file: {path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir")
    args = parser.parse_args()

    errors = validate(Path(args.skill_dir))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Skill export is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
