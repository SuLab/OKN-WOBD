#!/usr/bin/env python3
"""Summarize JSONL datasets collected from the NIAID API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


DEFAULT_INPUT_DIR = Path("data/raw")
DEFAULT_OUTPUT = Path("reports/jsonl_summary.md")


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
        help=f"Markdown file to write the summary (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def normalize_resource_name(stem: str) -> str:
    key = stem.lower()
    if key in RESOURCE_NAMES:
        return RESOURCE_NAMES[key]
    return stem.replace("_", " ").title()


def summarize_file(path: Path) -> dict[str, object]:
    total = 0
    disease_count = 0
    species_count = 0
    infectious_agent_count = 0
    all_three_count = 0

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            has_disease = bool(record.get("disease") or record.get("healthCondition"))
            has_species = bool(record.get("species"))
            has_agent = bool(record.get("infectiousAgent"))

            if has_disease:
                disease_count += 1

            if has_species:
                species_count += 1

            if has_agent:
                infectious_agent_count += 1

            # Count records with all three fields
            if has_disease and has_species and has_agent:
                all_three_count += 1

    return {
        "resource": normalize_resource_name(path.stem),
        "file": path.name,
        "total": total,
        "disease": disease_count,
        "species": species_count,
        "infectious_agent": infectious_agent_count,
        "all_three": all_three_count,
    }


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def generate_markdown(rows: list[dict[str, object]]) -> str:
    header = (
        "| Resource | File | Records | Disease | Infectious Agent | Species | Disease+InfectiousAgent+Species |\n"
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |\n"
    )
    body_lines: list[str] = []
    for row in rows:
        body_lines.append(
            f"| {row['resource']} | `{row['file']}` | {row['total']:,} | "
            f"{row['disease']:,} | {row['infectious_agent']:,} | {row['species']:,} | "
            f"{row['all_three']:,} |"
        )
    return header + "\n".join(body_lines) + ("\n" if body_lines else "")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    input_dir: Path = args.input_dir
    output: Path = args.output

    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    summaries = [summarize_file(path) for path in jsonl_files]
    markdown = generate_markdown(summaries)

    ensure_parent_directory(output)
    output.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nSummary saved to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

