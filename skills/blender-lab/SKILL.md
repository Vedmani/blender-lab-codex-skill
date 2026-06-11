---
name: blender-lab
description: Control Blender through the official Blender Lab MCP add-on without loading MCP tool definitions. Use when Codex needs to inspect or edit an open Blender scene, create geometry from prompts or floor plans, query objects/materials/collections, run Blender Python, render or screenshot the viewport, search bundled Blender API/manual docs, or analyze .blend files.
---

# Blender Lab

Use this skill instead of the Blender MCP server tool surface when possible. It keeps the token footprint small by calling Blender's Lab add-on bridge through `scripts/blender_lab.py`.

## Quick Start

Run commands from this skill directory:

```bash
uv run scripts/blender_lab.py objects-summary
uv run scripts/blender_lab.py object-detail --name Cube
uv run scripts/blender_lab.py execute --code 'import bpy; result = {"objects": len(bpy.data.objects)}'
```

Use `uv run` by default so the script metadata installs the right dependencies automatically. Plain `python scripts/blender_lab.py ...` may work for commands that only need the standard library, but `uv run` is the supported path for full functionality.

The wrapper reads `BLENDER_MCP_HOST` and `BLENDER_MCP_PORT`; defaults are `localhost` and `9874`.

## Workflow

Start every Blender task with a read-only inspection:

```bash
uv run scripts/blender_lab.py objects-summary
```

Prefer built-in commands over custom Python:

- Scene: `objects-summary`, `object-detail`, `datablocks-summary`, `path-info`, `usage-guess`, `missing-files`, `linked-libraries`, `window-layout-json`
- UI/navigation: `jump-workspace`, `jump-space-type`, `focus-object`, `focus-object-data`
- Images/renders: `screenshot-window`, `screenshot-area`, `render-viewport`, `render-thumbnail`
- Docs: `search-api`, `api-docs`, `search-manual`
- Background `.blend` files: `cli-execute`, `cli-datablocks-summary`, `cli-path-info`, `cli-usage-guess`, `cli-missing-files`, `cli-linked-libraries`

Use custom code only when no built-in command fits:

```bash
uv run scripts/blender_lab.py execute --code - <<'PY'
import bpy
result = {"active": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None}
PY
```

Always assign a JSON-serializable dict to `result`. For visible edits, create small changes, add an undo push when appropriate, and verify with a read-back command.

Run Blender bridge commands sequentially. Do not launch multiple live bridge calls in parallel against the same open Blender session.

## Safety

Respect the user's current file and scene structure.

- Do not save, export, delete, purge, or destructively modify content unless explicitly requested.
- Do not assume object names, active selection, mode, units, collections, or visibility; inspect first.
- For operators, ensure the correct mode, active object, and selection.
- Prefer non-destructive modifiers and new clearly named objects/materials for exploratory changes.
- Preserve Blender Lab upstream notices in vendored resources.

## References

- `scripts/blender_lab.py`: command wrapper.
- `references/blmcp/`: vendored official Blender Lab tool-code, helpers, and bundled docs.
- `references/UPSTREAM.md`: provenance and license metadata.
