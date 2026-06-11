# Blender Lab Codex Skill

This repository exports the `blender-lab` Codex skill.

The skill lets Codex control an open Blender session through the official Blender Lab MCP add-on bridge without loading the Blender MCP tool definitions into every turn. It also bundles the official Blender Lab tool code and Blender API/manual docs used by the wrapper.

## Install

Install with the Codex skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo Vedmani/blender-lab-codex-skill \
  --path skills/blender-lab
```

Or from the repository URL:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --url https://github.com/Vedmani/blender-lab-codex-skill/tree/main/skills/blender-lab
```

## Requirements

- Blender with the official Blender Lab MCP add-on installed and running.
- The add-on bridge listening on `localhost:9874`, or set `BLENDER_MCP_HOST` and `BLENDER_MCP_PORT`.
- `uv` available on `PATH`; the skill wrapper uses script metadata so dependencies are resolved by `uv run`.

## Layout

- `skills/blender-lab/SKILL.md`: skill metadata and usage workflow.
- `skills/blender-lab/scripts/blender_lab.py`: command wrapper for the Blender Lab bridge.
- `skills/blender-lab/references/blmcp/`: vendored official Blender Lab tool code and docs.
- `skills/blender-lab/references/UPSTREAM.md`: upstream provenance and license metadata.

## Validate

```bash
python3 scripts/validate_skill.py skills/blender-lab
```

For a local Codex installation, you can also run:

```bash
uv run --with pyyaml python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/blender-lab
```

## License

This repository is licensed under `GPL-3.0-or-later` because it vendors Blender Lab MCP code declared under that license. See `skills/blender-lab/references/UPSTREAM.md` for upstream provenance.
