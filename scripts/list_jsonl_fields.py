#!/usr/bin/env python3
"""List top-level JSON fields for each JSONL dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_INPUT_DIR = Path("data/raw")
DEFAULT_OUTPUT = Path("reports/jsonl_fields.md")

RESOURCE_NAMES = {
    "immport": "ImmPort",
    "vdjserver": "VDJ Server",
    "vivli": "Vivli",
    "radx_data_hub": "RADx Data Hub",
    "project_tycho": "Project Tycho",
    "protein_data_bank": "Protein Data Bank",
    "pdb": "Protein Data Bank",
}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing JSONL files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Markdown file to write the field lists (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def normalize_resource_name(stem: str) -> str:
    key = stem.lower()
    if key in RESOURCE_NAMES:
        return RESOURCE_NAMES[key]
    return stem.replace("_", " ").title()


def collect_fields(path: Path) -> Sequence[str]:
    keys: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.update(record.keys())
    return tuple(sorted(keys))


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def generate_markdown(rows: list[tuple[str, str, Sequence[str]]]) -> str:
    sections: list[str] = ["# JSONL Top-Level Fields\n"]
    for resource, filename, fields in rows:
        sections.append(f"## {resource}\n")
        sections.append(f"*File:* `{filename}`\n")
        if fields:
            sections.append("\n".join(f"- `{field}`" for field in fields))
        else:
            sections.append("_No fields found._")
        sections.append("")  # blank line between sections
    return "\n".join(sections).rstrip() + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    input_dir: Path = args.input_dir
    output: Path = args.output

    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    rows: list[tuple[str, str, Sequence[str]]] = []
    for path in jsonl_files:
        fields = collect_fields(path)
        rows.append((normalize_resource_name(path.stem), path.name, fields))

    markdown = generate_markdown(rows)
    ensure_parent_directory(output)
    output.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nField list saved to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

