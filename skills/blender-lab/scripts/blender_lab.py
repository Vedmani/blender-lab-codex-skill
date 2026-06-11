#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=11.0.0"]
# ///
"""Shell wrapper for the Blender Lab MCP add-on bridge.

This script intentionally avoids starting an MCP server. It exposes the same
default Blender Lab capabilities as compact CLI commands that return JSON.
"""

from __future__ import annotations

import argparse
from collections import namedtuple
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = SKILL_DIR / "references"
sys.path.insert(0, str(VENDOR_DIR))

from blmcp.tools_helpers import (  # noqa: E402
    toolcode_format_call,
    toolcode_load_from_filepath,
    toolcode_wrap_with_calling_convention,
)
from blmcp.tools_helpers.blender_cli import run_blender_cli, synced_blend_for_cli  # noqa: E402
from blmcp.tools_helpers.connection import send_code  # noqa: E402


TOOLS_DIR = VENDOR_DIR / "blmcp" / "tools"
DATA_DIR = VENDOR_DIR / "blmcp" / "data"


LIVE_TOOL_MODULES = {
    "objects-summary": "get_objects_summary",
    "object-detail": "get_object_detail_summary",
    "datablocks-summary": "get_blendfile_summary_datablocks",
    "path-info": "get_blendfile_summary_path_info",
    "usage-guess": "get_blendfile_summary_usage_guess",
    "missing-files": "get_blendfile_summary_missing_files",
    "linked-libraries": "get_blendfile_summary_of_linked_libraries",
    "window-layout-json": "get_screenshot_of_window_as_json",
    "jump-workspace": "jump_to_tab_by_name",
    "jump-space-type": "jump_to_tab_by_space_type",
    "focus-object": "jump_to_view3d_object_by_name",
    "focus-object-data": "jump_to_view3d_object_data_by_name",
    "render-viewport": "render_viewport_to_path",
    "render-thumbnail": "render_thumbnail_to_path",
}

CLI_TOOL_MODULES = {
    "cli-datablocks-summary": "get_blendfile_summary_datablocks",
    "cli-path-info": "get_blendfile_summary_path_info",
    "cli-usage-guess": "get_blendfile_summary_usage_guess",
    "cli-missing-files": "get_blendfile_summary_missing_files",
    "cli-linked-libraries": "get_blendfile_summary_of_linked_libraries",
}


def _json_dump(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=repr))


def _read_code(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return value


def _params_for_tool(module_name: str, kwargs: dict[str, Any]) -> Any:
    if not kwargs:
        return None
    fields = _params_fields_for_tool(module_name)
    params_cls = namedtuple("Params", fields)
    return params_cls(**kwargs)


def _params_fields_for_tool(module_name: str) -> list[str]:
    path = TOOLS_DIR / f"{module_name}_toolcode.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?ms)^class Params\(NamedTuple\):\n(?P<body>.*?)(?=^\S|\Z)", text)
    if not match:
        raise ValueError(f"No Params NamedTuple found for {module_name}")
    fields: list[str] = []
    for line in match.group("body").splitlines():
        field = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if field:
            fields.append(field.group(1))
    if not fields:
        raise ValueError(f"No Params fields found for {module_name}")
    return fields


def _tool_code(module_name: str, params: Any) -> str:
    wrapper_path = TOOLS_DIR / f"{module_name}.py"
    toolcode = toolcode_wrap_with_calling_convention(
        toolcode_load_from_filepath(str(wrapper_path))
    )
    return toolcode_format_call(toolcode, params)


def _send_tool(module_name: str, params: Any) -> dict[str, Any]:
    return send_code(_tool_code(module_name, params), strict_json=True)


def _unwrap_response(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") != "ok":
        return response
    result = response.get("result")
    if isinstance(result, dict):
        return result
    return response


def cmd_execute(args: argparse.Namespace) -> dict[str, Any]:
    return send_code(_read_code(args.code), strict_json=False)


def cmd_cli_execute(args: argparse.Namespace) -> dict[str, Any]:
    with synced_blend_for_cli(args.blend_file) as synced_path:
        return run_blender_cli(synced_path, _read_code(args.code))


def cmd_live_tool(args: argparse.Namespace) -> dict[str, Any]:
    module_name = LIVE_TOOL_MODULES[args.command]
    kwargs: dict[str, Any] = {}
    for key in (
        "name",
        "space_type",
        "allow_edits",
        "output_path",
    ):
        if hasattr(args, key):
            kwargs[key] = getattr(args, key)
    return _send_tool(module_name, _params_for_tool(module_name, kwargs))


def cmd_cli_tool(args: argparse.Namespace) -> dict[str, Any]:
    module_name = CLI_TOOL_MODULES[args.command]
    with synced_blend_for_cli(args.blend_file) as synced_path:
        return run_blender_cli(synced_path, _tool_code(module_name, None))


def cmd_screenshot_window(args: argparse.Namespace) -> dict[str, Any]:
    del args.size_limit
    output = str(Path(args.output).expanduser())
    code = (
        "import bpy, os\n"
        "filepath = {!r}\n"
        "os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)\n"
        "try:\n"
        "    bpy.ops.screen.screenshot(filepath=filepath)\n"
        "    result = {{'status': 'ok', 'filepath': filepath, 'bytes': os.path.getsize(filepath)}}\n"
        "except Exception as ex:\n"
        "    result = {{'status': 'error', 'message': str(ex), 'filepath': filepath}}\n"
    ).format(output)
    return _unwrap_response(send_code(code, strict_json=True))


def cmd_screenshot_area(args: argparse.Namespace) -> dict[str, Any]:
    del args.size_limit
    from PIL import Image

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="blender_lab_screenshot_") as tmpdir:
        full = Path(tmpdir) / "window.png"
        window_result = argparse.Namespace(output=str(full), size_limit=0)
        response = cmd_screenshot_window(window_result)
        if response.get("status") != "ok":
            return response
        with Image.open(full) as image:
            crop = image.crop((args.x, args.y, args.x + args.width, args.y + args.height))
            crop.save(output)
    return {"status": "ok", "filepath": str(output), "bytes": output.stat().st_size}


STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "can",
    "do", "does", "for", "from", "how", "if", "in", "is", "it",
    "its", "not", "of", "on", "or", "that", "the", "this", "to",
    "was", "were", "what", "when", "where", "which", "why", "will",
    "with", "you", "your",
}


def _doc_root(scope: str) -> Path:
    if scope not in {"api", "manual"}:
        raise ValueError("scope must be 'api' or 'manual'")
    return DATA_DIR / scope


def _query_tokens(query: str) -> list[str]:
    return [
        token.lower()
        for token in re.split(r"[-_./\s]+", query)
        if token and token.lower() not in STOPWORDS
    ]


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n+", text)
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if chunk.strip()]


def _breadcrumb_before(text: str) -> str:
    lines = text.splitlines()
    titles: list[str] = []
    for index, line in enumerate(lines[:-1]):
        title = line.strip()
        underline = lines[index + 1].strip()
        if title and underline and len(set(underline)) == 1 and underline[0] in "=-~^\"#*+":
            titles.append(title)
    return " > ".join(titles[-4:])


def _search_docs(args: argparse.Namespace, scope: str) -> dict[str, Any]:
    root = _doc_root(scope)
    tokens = _query_tokens(args.query)
    if not tokens:
        return {"status": "ok", "query": args.query, "scope": scope, "hits": []}

    hits: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.rst")):
        rel = path.relative_to(DATA_DIR).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        paragraphs = _paragraphs(text)
        path_surface = rel.lower().replace(".rst", "")
        for idx, para in enumerate(paragraphs):
            before = "\n\n".join(paragraphs[: idx + 1])
            breadcrumb = _breadcrumb_before(before)
            surface = " ".join((path_surface, breadcrumb.lower(), para.lower()))
            if not all(token in surface for token in tokens):
                continue
            start = max(0, idx - args.context)
            end = min(len(paragraphs), idx + args.context + 1)
            score = sum(surface.count(token) for token in tokens)
            if any(token in path_surface for token in tokens):
                score += 5
            hits.append(
                {
                    "path": rel,
                    "text": "\n\n".join(paragraphs[start:end]),
                    "breadcrumb": breadcrumb,
                    "index": len(hits),
                    "score": score,
                }
            )
    hits.sort(key=lambda h: (-int(h["score"]), str(h["path"]), int(h["index"])))
    for idx, hit in enumerate(hits):
        hit["index"] = idx
    if args.index is not None:
        hits = [hits[args.index]] if 0 <= args.index < len(hits) else []
    else:
        hits = hits[: args.max_results]
    return {"status": "ok", "query": args.query, "scope": scope, "hits": hits}


def _api_docs_direct(identifier: str) -> dict[str, Any]:
    api_root = _doc_root("api")
    if identifier == "*":
        modules = sorted({path.stem.split(".", 1)[0] for path in api_root.glob("*.rst")})
        return {"kind": "namespace", "found": True, "identifier": identifier, "submodules": modules}
    if identifier.endswith(".*"):
        prefix = identifier[:-2]
        children = sorted(
            path.stem
            for path in api_root.glob(prefix + ".*.rst")
            if path.stem.count(".") == prefix.count(".") + 1
        )
        return {"kind": "namespace", "found": bool(children), "identifier": identifier, "submodules": children}

    direct = api_root / f"{identifier}.rst"
    if direct.exists():
        content = direct.read_text(encoding="utf-8", errors="replace")
        if len(content) > 32 * 1024:
            defs = re.findall(r"^\.\. (?:class|function|method|attribute|data)::\s+([^\n(]+)", content, re.M)
            content = (
                f"File too large to inline ({len(content) // 1024} KB); "
                f"query individual members as `{identifier}.<name>`:\n\n"
                + "\n".join(f"- {item.strip()}" for item in defs[:500])
            )
        return {"kind": "exact", "found": True, "identifier": identifier, "content": content, "examples": []}

    parts = identifier.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:cut])
        tail = ".".join(parts[cut:])
        parent_path = api_root / f"{parent}.rst"
        if not parent_path.exists():
            continue
        content = parent_path.read_text(encoding="utf-8", errors="replace")
        member = re.escape(tail.split(".")[-1])
        pattern = re.compile(
            r"(?ms)^(\.\. (?:class|function|method|attribute|data)::[^\n]*"
            + member
            + r"[^\n]*\n.*?)(?=^\.\. (?:class|function|method|attribute|data)::|\Z)"
        )
        match = pattern.search(content)
        if match:
            return {
                "kind": "definition",
                "found": True,
                "identifier": identifier,
                "content": match.group(1).strip(),
                "examples": [],
            }
        siblings = sorted(path.stem for path in api_root.glob(parent + ".*.rst"))
        return {
            "kind": "partial",
            "found": False,
            "identifier": identifier,
            "parent": parent,
            "available": [],
            "submodules": siblings[:200],
        }

    suggestions = sorted(path.stem for path in api_root.glob(f"*{parts[-1]}*.rst"))[:50]
    return {"kind": "suggestions" if suggestions else "missing", "found": False, "identifier": identifier, "suggestions": suggestions}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Blender Lab bridge commands without an MCP server.")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in (
        "objects-summary",
        "datablocks-summary",
        "path-info",
        "usage-guess",
        "missing-files",
        "linked-libraries",
        "window-layout-json",
    ):
        p = sub.add_parser(name)
        p.set_defaults(func=cmd_live_tool)

    p = sub.add_parser("object-detail")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_live_tool)

    p = sub.add_parser("jump-workspace")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_live_tool)

    p = sub.add_parser("jump-space-type")
    p.add_argument("--space-type", required=True)
    p.add_argument("--allow-edits", action="store_true")
    p.set_defaults(func=cmd_live_tool)

    for name in ("focus-object", "focus-object-data"):
        p = sub.add_parser(name)
        p.add_argument("--name", required=True)
        p.add_argument("--allow-edits", action="store_true")
        p.set_defaults(func=cmd_live_tool)

    for name in ("render-viewport", "render-thumbnail"):
        p = sub.add_parser(name)
        p.add_argument("--output", dest="output_path", required=True)
        p.set_defaults(func=cmd_live_tool)

    p = sub.add_parser("execute")
    p.add_argument("--code", required=True, help="Python code, or '-' to read from stdin")
    p.set_defaults(func=cmd_execute)

    p = sub.add_parser("screenshot-window")
    p.add_argument("--output", required=True)
    p.add_argument("--size-limit", type=int, default=0)
    p.set_defaults(func=cmd_screenshot_window)

    p = sub.add_parser("screenshot-area")
    p.add_argument("--output", required=True)
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--y", type=int, required=True)
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--size-limit", type=int, default=0)
    p.set_defaults(func=cmd_screenshot_area)

    p = sub.add_parser("search-api")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=20)
    p.add_argument("--context", type=int, default=0)
    p.add_argument("--index", type=int)
    p.set_defaults(func=lambda args: _search_docs(args, "api"))

    p = sub.add_parser("search-manual")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=20)
    p.add_argument("--context", type=int, default=0)
    p.add_argument("--index", type=int)
    p.set_defaults(func=lambda args: _search_docs(args, "manual"))

    p = sub.add_parser("api-docs")
    p.add_argument("--identifier", required=True)
    p.set_defaults(func=lambda args: _api_docs_direct(args.identifier))

    p = sub.add_parser("cli-execute")
    p.add_argument("--blend-file", required=True)
    p.add_argument("--code", required=True, help="Python code, or '-' to read from stdin")
    p.set_defaults(func=cmd_cli_execute)

    for name in CLI_TOOL_MODULES:
        p = sub.add_parser(name)
        p.add_argument("--blend-file", required=True)
        p.set_defaults(func=cmd_cli_tool)

    return parser


def main() -> int:
    # Match this user's verified Blender Lab add-on preferences unless overridden.
    os.environ.setdefault("BLENDER_MCP_HOST", "localhost")
    os.environ.setdefault("BLENDER_MCP_PORT", "9874")
    args = build_parser().parse_args()
    try:
        _json_dump(args.func(args))
        return 0
    except Exception as ex:  # Keep shell contract JSON-shaped on failure.
        _json_dump({"status": "error", "message": str(ex), "error_type": type(ex).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
