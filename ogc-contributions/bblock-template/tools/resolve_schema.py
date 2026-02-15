#!/usr/bin/env python3
"""
Resolve OGC Building Block schemas into a single complete JSON Schema.

Recursively resolves ALL $ref references from the modular YAML/JSON source
schemas into one fully-inlined schema -- purely for validation and inspection,
with no form simplifications.

The OGC bblocks-postprocess Docker tool generates annotated schemas in
build/annotated/, but these still contain $ref references to remote URLs.
This script fills the gap by producing a fully-resolved, self-contained
JSON Schema from the source files in _sources/.

$ref patterns handled:
  1. Relative path:       $ref: ../detailEMPA/schema.yaml
  2. Fragment-only:       $ref: '#/$defs/Identifier'
  3. Cross-file fragment: $ref: ../metaMetadata/schema.yaml#/$defs/conformsTo_item
  4. Both YAML and JSON file extensions

Usage:
    python tools/resolve_schema.py --file _sources/myFeature/schema.yaml
    python tools/resolve_schema.py --bblock myFeature
    python tools/resolve_schema.py --bblock myFeature --sources-dir _sources
    python tools/resolve_schema.py --file schema.yaml --flatten-allof -o resolved.json
    python tools/resolve_schema.py --file schema.yaml --keep-metadata
"""

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml is required but not installed.\n"
        "Install with:  pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)

# Keys to strip from schemas by default (metadata, not useful for validation)
DEFAULT_STRIP_KEYS = {"$id", "x-jsonld-prefixes", "x-jsonld-context", "x-jsonld-extra-terms"}


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_schema_file(path: Path) -> dict:
    """Load a schema file (YAML or JSON) based on extension."""
    with open(path, "r", encoding="utf-8") as f:
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f) or {}
        else:
            return json.load(f)


# ---------------------------------------------------------------------------
# JSON Pointer resolution
# ---------------------------------------------------------------------------

def resolve_fragment(schema: dict, pointer: str) -> Any:
    """Resolve a JSON Pointer (e.g., '/$defs/Identifier') within a schema."""
    parts = pointer.lstrip("/").split("/")
    current = schema
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(f"Cannot resolve pointer /{'/'.join(parts)} at part '{part}'")
    return current


# ---------------------------------------------------------------------------
# Metadata stripping
# ---------------------------------------------------------------------------

def strip_metadata_keys(schema: Any, strip_keys: set = None, is_root: bool = True) -> Any:
    """Recursively remove $id, x-jsonld-*, and nested $schema keys.

    Parameters
    ----------
    schema : Any
        The schema node to process.
    strip_keys : set, optional
        Set of top-level key names to strip. Defaults to DEFAULT_STRIP_KEYS.
        Keys starting with ``x-jsonld`` are always stripped regardless.
    is_root : bool
        Whether this is the root schema node (preserves $schema at root).
    """
    if strip_keys is None:
        strip_keys = DEFAULT_STRIP_KEYS
    if isinstance(schema, dict):
        result = {}
        for k, v in schema.items():
            if k in strip_keys:
                continue
            if k.startswith("x-jsonld"):
                continue
            if k == "$schema" and not is_root:
                continue
            result[k] = strip_metadata_keys(v, strip_keys=strip_keys, is_root=False)
        return result
    elif isinstance(schema, list):
        return [strip_metadata_keys(item, strip_keys=strip_keys, is_root=False) for item in schema]
    return schema


# ---------------------------------------------------------------------------
# Deep merge (for allOf flattening)
# ---------------------------------------------------------------------------

_SCHEMA_DEF_KEYS = frozenset({"type", "oneOf", "anyOf", "allOf", "$ref"})


def _is_complete_schema(d: dict) -> bool:
    """Return True if d looks like a complete schema definition (has type, composition, or $ref)."""
    return bool(d.keys() & _SCHEMA_DEF_KEYS)


def deep_merge(base: dict, overlay: dict) -> dict:
    """
    Deep merge overlay into base. Overlay values take precedence.
    For dicts, merge recursively. For everything else, overlay replaces base.

    Special handling for ``properties`` dicts: when an overlay provides a
    property definition that already exists in the base AND the overlay looks
    like a complete schema definition (has ``type``, ``oneOf``, ``anyOf``,
    ``allOf``, or ``$ref``), the overlay **replaces** the base definition
    entirely.  This prevents invalid schemas where, e.g., two composed schemas
    define the same property with incompatible composition keywords.

    When the overlay is a partial constraint patch (no ``type`` or composition
    keywords at the property level -- just nested ``items.properties...``), it is
    deep-merged so that the base structure (``type``, ``description``, ``oneOf``,
    etc.) is preserved alongside the new constraints.
    """
    return _deep_merge_inner(base, overlay, in_properties=False)


def _deep_merge_inner(base: dict, overlay: dict, in_properties: bool) -> dict:
    result = copy.deepcopy(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            if in_properties and _is_complete_schema(v):
                # Complete property definition -> replace entirely
                result[k] = copy.deepcopy(v)
            elif k == "properties":
                result[k] = _deep_merge_inner(result[k], v, in_properties=True)
            else:
                result[k] = _deep_merge_inner(result[k], v, in_properties=False)
        else:
            result[k] = copy.deepcopy(v)
    return result


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------

def resolve_file(path: Path, seen: set) -> dict:
    """Load a YAML or JSON schema file and resolve all $ref within it."""
    canonical = path.resolve()
    if canonical in seen:
        return {"$comment": f"circular ref to {canonical}"}
    seen = seen | {canonical}  # Copy to avoid mutation across branches

    schema = load_schema_file(canonical)
    if not isinstance(schema, dict):
        return schema

    # Resolve $defs so fragment-only refs (#/$defs/X) can find them.
    # Two-pass strategy:
    #   Pass 1 -- resolve every def with an empty local-defs dict.  This expands
    #            all external file $refs but leaves cross-def fragment refs as
    #            "$comment: unresolved ..." placeholders.
    #   Pass 2 -- re-resolve every def, this time with the fully-populated defs
    #            dict so that cross-def fragment refs can be found.
    defs = {}
    if "$defs" in schema:
        raw_defs = schema["$defs"]
        for def_name, def_schema in raw_defs.items():
            defs[def_name] = resolve_node(def_schema, canonical.parent, {}, seen)
        # Pass 2: re-resolve with full defs.  Because pass 1 may have left
        # "$comment" placeholders instead of the resolved content, we also
        # inline those placeholders by re-walking the defs.
        for def_name in list(defs.keys()):
            defs[def_name] = _inline_unresolved_defs(defs[def_name], defs, canonical.parent, seen)

    # Walk and resolve the entire schema
    resolved = resolve_node(schema, canonical.parent, defs, seen)

    # Remove $defs from final output (they've been inlined)
    if isinstance(resolved, dict):
        resolved.pop("$defs", None)

    return resolved


def resolve_node(node: Any, base_dir: Path, defs: dict, seen: set) -> Any:
    """Recursively resolve $ref in a schema node."""
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            resolved = _resolve_ref(ref, base_dir, defs, seen)

            # If $ref has sibling keys, merge resolved with siblings
            siblings = {k: v for k, v in node.items() if k != "$ref"}
            if siblings:
                siblings = resolve_node(siblings, base_dir, defs, seen)
                if isinstance(resolved, dict):
                    resolved = deep_merge(resolved, siblings)
                # If resolved is not a dict (unlikely), siblings are lost
            return resolved

        # Recurse into all dict values
        result = {}
        for k, v in node.items():
            result[k] = resolve_node(v, base_dir, defs, seen)
        return result

    elif isinstance(node, list):
        return [resolve_node(item, base_dir, defs, seen) for item in node]

    return node


def _inline_unresolved_defs(node: Any, defs: dict, base_dir: Path, seen: set) -> Any:
    """
    Walk *node* and replace ``{"$comment": "unresolved fragment ref: #/$defs/X"}``
    placeholders with the actual resolved content from *defs*.
    Also re-resolve any remaining $ref nodes with the full defs dict.
    """
    if isinstance(node, dict):
        # Check for placeholder left by pass 1
        if "$comment" in node and len(node) == 1:
            comment = node["$comment"]
            if comment.startswith("unresolved fragment ref: #/$defs/"):
                def_name = comment.split("/")[-1]
                if def_name in defs:
                    return copy.deepcopy(defs[def_name])
        # Also resolve any leftover $ref
        if "$ref" in node:
            ref = node["$ref"]
            resolved = _resolve_ref(ref, base_dir, defs, seen)
            siblings = {k: v for k, v in node.items() if k != "$ref"}
            if siblings:
                siblings = _inline_unresolved_defs(siblings, defs, base_dir, seen)
                if isinstance(resolved, dict):
                    resolved = deep_merge(resolved, siblings)
            return resolved
        result = {}
        for k, v in node.items():
            result[k] = _inline_unresolved_defs(v, defs, base_dir, seen)
        return result
    elif isinstance(node, list):
        return [_inline_unresolved_defs(item, defs, base_dir, seen) for item in node]
    return node


def _resolve_ref(ref: str, base_dir: Path, defs: dict, seen: set) -> Any:
    """Parse and resolve a $ref string."""
    if ref.startswith("#/"):
        # Fragment-only ref (e.g., #/$defs/Identifier)
        pointer = ref[1:]  # Strip leading #
        # Try the local defs dict first
        parts = pointer.lstrip("/").split("/")
        if len(parts) == 2 and parts[0] == "$defs" and parts[1] in defs:
            return copy.deepcopy(defs[parts[1]])
        # Fall through: shouldn't happen if $defs were resolved, but handle gracefully
        return {"$comment": f"unresolved fragment ref: {ref}"}

    # File ref, possibly with fragment
    if "#" in ref:
        file_part, fragment = ref.split("#", 1)
    else:
        file_part, fragment = ref, None

    file_path = (base_dir / file_part).resolve()
    if not file_path.exists():
        return {"$comment": f"file not found: {file_path}"}

    resolved = resolve_file(file_path, seen)

    if fragment:
        try:
            resolved = resolve_fragment(resolved, fragment)
        except KeyError as e:
            return {"$comment": f"could not resolve fragment {fragment} in {file_path}: {e}"}
        # The fragment result might itself contain refs -- resolve them
        resolved = resolve_node(resolved, file_path.parent, {}, seen)

    return resolved


# ---------------------------------------------------------------------------
# allOf flattening (optional)
# ---------------------------------------------------------------------------

def flatten_allof(schema: Any) -> Any:
    """
    Recursively flatten allOf entries into a single object.
    Merges properties, required, and other constraints from all allOf entries.
    Preserves anyOf/oneOf as-is (they represent valid polymorphic choices).
    """
    if isinstance(schema, dict):
        # Recurse first so nested allOf in properties/items are handled
        result = {}
        for k, v in schema.items():
            result[k] = flatten_allof(v)

        # Now flatten allOf in the current object
        if "allOf" in result:
            all_of = result.pop("allOf")
            merged = {}
            # Collect all non-allOf keys from the current object
            for k, v in result.items():
                merged[k] = v

            for entry in all_of:
                if isinstance(entry, dict):
                    merged = deep_merge(merged, entry)

            return merged

        return result

    elif isinstance(schema, list):
        return [flatten_allof(item) for item in schema]

    return schema


# ---------------------------------------------------------------------------
# Building block discovery
# ---------------------------------------------------------------------------

def find_bblock_schema(name: str, sources_dir: Path) -> Path:
    """Find the schema entry point for a building block by name.

    Search order:
      1. {sources_dir}/{name}/schema.yaml       (flat layout)
      2. {sources_dir}/{name}/schema.json        (flat layout, JSON)
      3. {sources_dir}/**/{name}/schema.yaml     (nested layout, must have bblock.json)
      4. {sources_dir}/**/{name}/schema.json     (nested layout, JSON fallback)
    """
    # Flat layout
    flat_yaml = sources_dir / name / "schema.yaml"
    if flat_yaml.exists():
        return flat_yaml
    flat_json = sources_dir / name / "schema.json"
    if flat_json.exists():
        return flat_json

    # Nested layout -- search recursively for directories matching the name
    for bblock_json in sorted(sources_dir.rglob("bblock.json")):
        bblock_dir = bblock_json.parent
        if bblock_dir.name == name:
            yaml_path = bblock_dir / "schema.yaml"
            if yaml_path.exists():
                return yaml_path
            json_path = bblock_dir / "schema.json"
            if json_path.exists():
                return json_path

    print(f"ERROR: Cannot find schema for building block '{name}'", file=sys.stderr)
    print(f"  Searched in: {sources_dir}", file=sys.stderr)
    sys.exit(1)


def _detect_sources_dir() -> Path:
    """Auto-detect the _sources directory relative to the script or CWD."""
    # Relative to script location (tools/ lives next to _sources/)
    script_based = Path(__file__).resolve().parent.parent / "_sources"
    if script_based.is_dir():
        return script_based

    # Relative to CWD
    cwd_based = Path.cwd() / "_sources"
    if cwd_based.is_dir():
        return cwd_based

    return script_based  # Fall back; will produce clear error later


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Resolve OGC Building Block schemas into a single complete JSON Schema.",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        type=Path,
        help="Resolve an arbitrary schema file by path",
    )
    input_group.add_argument(
        "--bblock",
        help="Resolve a building block by name (searches --sources-dir)",
    )

    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=None,
        help="Path to the _sources directory (auto-detected if omitted)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Write output to file (default: stdout)",
    )
    parser.add_argument(
        "--flatten-allof",
        action="store_true",
        help="Merge allOf entries into single objects",
    )
    parser.add_argument(
        "--keep-metadata",
        action="store_true",
        help="Keep $id, x-jsonld-*, and other metadata keys (stripped by default)",
    )
    parser.add_argument(
        "--strip-keys",
        nargs="*",
        default=None,
        help="Custom set of keys to strip (overrides defaults; ignored with --keep-metadata)",
    )
    args = parser.parse_args()

    if args.file:
        schema_path = args.file.resolve()
        if not schema_path.exists():
            print(f"ERROR: File not found: {schema_path}", file=sys.stderr)
            sys.exit(1)
    else:
        sources_dir = args.sources_dir or _detect_sources_dir()
        sources_dir = sources_dir.resolve()
        if not sources_dir.is_dir():
            print(f"ERROR: Sources directory not found: {sources_dir}", file=sys.stderr)
            sys.exit(1)
        schema_path = find_bblock_schema(args.bblock, sources_dir)

    print(f"Resolving: {schema_path}", file=sys.stderr)

    # Resolve all $ref recursively
    resolved = resolve_file(schema_path, seen=set())

    # Strip metadata keys (unless --keep-metadata)
    if not args.keep_metadata:
        strip_keys = set(args.strip_keys) if args.strip_keys is not None else DEFAULT_STRIP_KEYS
        resolved = strip_metadata_keys(resolved, strip_keys=strip_keys, is_root=True)

    # Optionally flatten allOf
    if args.flatten_allof:
        resolved = flatten_allof(resolved)

    # Output
    output_json = json.dumps(resolved, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Wrote: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(output_json)


if __name__ == "__main__":
    main()
