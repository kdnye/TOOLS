#!/usr/bin/env python3
"""Generate individualized text files from a CSV using a simple template."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from string import Formatter
from typing import Dict, Iterable, List, Sequence, Set


UNIQUE_ID_COLUMN = "id"


class MissingColumnError(Exception):
    """Raised when required CSV columns are missing."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one text file per CSV row by substituting CSV fields into a "
            "text template."
        )
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path to the CSV file containing merge data.",
    )
    parser.add_argument(
        "--template",
        required=True,
        type=Path,
        help="Path to the text template with Python format-style placeholders.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where the rendered text files should be written.",
    )
    return parser.parse_args(argv)


def load_template(template_path: Path) -> str:
    try:
        return template_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - simple I/O failure message
        print(f"Error reading template: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def required_fields_from_template(template: str) -> Set[str]:
    formatter = Formatter()
    fields: Set[str] = set()
    for literal_text, field_name, format_spec, conversion in formatter.parse(template):
        if field_name is None or field_name == "":
            continue
        if field_name.endswith("!r"):
            # Formatter.parse already splits conversion, but guard against malformed
            field_name = field_name[:-2]
        fields.add(field_name)
    return fields


def validate_columns(fieldnames: Sequence[str] | None, required_fields: Set[str]) -> None:
    if not fieldnames:
        raise MissingColumnError("CSV file is missing a header row.")

    missing_required = [field for field in required_fields if field not in fieldnames]
    if missing_required:
        raise MissingColumnError(
            "CSV is missing required columns: " + ", ".join(sorted(missing_required))
        )

    if UNIQUE_ID_COLUMN not in fieldnames:
        raise MissingColumnError(
            f"CSV is missing the unique identifier column '{UNIQUE_ID_COLUMN}'."
        )


def sanitized_filename(identifier: str) -> str:
    safe_id = identifier.strip()
    if not safe_id:
        raise ValueError("Identifier is empty after stripping whitespace.")
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in safe_id)
    return f"{sanitized}.txt"


def gather_missing_fields(row: Dict[str, str], required_fields: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for field in required_fields:
        value = row.get(field, "")
        if value is None or str(value).strip() == "":
            missing.append(field)
    return missing


def render_template(template: str, row: Dict[str, str]) -> str:
    class RowDict(dict):
        def __missing__(self, key: str) -> str:  # pragma: no cover - defensive
            raise KeyError(key)

    return template.format_map(RowDict(row))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    template = load_template(args.template)
    required_fields = required_fields_from_template(template)
    required_fields.add(UNIQUE_ID_COLUMN)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated: List[str] = []
    skipped: Dict[str, List[str]] = {}

    try:
        with args.csv.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            validate_columns(reader.fieldnames, required_fields)

            for index, row in enumerate(reader, start=2):  # start=2 to reflect CSV line
                identifier = row.get(UNIQUE_ID_COLUMN, "").strip()
                if not identifier:
                    skipped[f"<row {index}>"] = [UNIQUE_ID_COLUMN]
                    continue

                missing_fields = gather_missing_fields(row, required_fields)
                if missing_fields:
                    skipped[identifier] = missing_fields
                    continue

                try:
                    content = render_template(template, row)
                except KeyError as exc:
                    skipped[identifier] = [str(exc)]
                    continue

                try:
                    filename = sanitized_filename(identifier)
                except ValueError:
                    skipped[identifier] = [UNIQUE_ID_COLUMN]
                    continue

                output_path = args.output_dir / filename
                output_path.write_text(content, encoding="utf-8")
                generated.append(str(output_path))
    except MissingColumnError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 1

    print("Mail merge summary:")
    print(f"  Generated {len(generated)} drafts.")
    for path in generated:
        print(f"    - {path}")

    if skipped:
        print(f"  Skipped {len(skipped)} rows due to missing fields:")
        for identifier, fields in skipped.items():
            field_list = ", ".join(sorted(fields))
            print(f"    - {identifier}: missing {field_list}")
    else:
        print("  No missing fields detected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
