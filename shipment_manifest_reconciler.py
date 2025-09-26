"""Shipment manifest reconciliation tool.

This script compares expected shipment manifests against scanned results and
reports matched, short, and overage quantities per order and SKU.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

REQUIRED_COLUMNS = {"order_id", "sku", "quantity"}


@dataclass
class ReconciliationRow:
    order_id: str
    sku: str
    expected: int
    scanned: int
    matched: int
    short: int
    overage: int

    @classmethod
    def from_counts(cls, key: Tuple[str, str], expected: int, scanned: int) -> "ReconciliationRow":
        order_id, sku = key
        matched = min(expected, scanned)
        short = max(expected - scanned, 0)
        overage = max(scanned - expected, 0)
        return cls(
            order_id=order_id,
            sku=sku,
            expected=expected,
            scanned=scanned,
            matched=matched,
            short=short,
            overage=overage,
        )


def parse_arguments(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile expected vs scanned shipment manifests.")
    parser.add_argument("--expected", required=True, help="Path to the expected manifest CSV file.")
    parser.add_argument("--scanned", required=True, help="Path to the scanned manifest CSV file.")
    parser.add_argument(
        "--export",
        help="Optional destination path for the reconciliation results (CSV). A Markdown file with the same stem will also be produced.",
    )
    return parser.parse_args(argv)


def load_manifest(path: Path) -> Counter[Tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    counter: Counter[Tuple[str, str]] = Counter()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"CSV file {path} is missing required columns: {', '.join(sorted(missing_columns))}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                order_id = row["order_id"].strip()
                sku = row["sku"].strip()
                quantity = int(row["quantity"].strip())
            except (AttributeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid data at {path}:{line_number}. Expected non-empty order_id, sku, and integer quantity."
                ) from exc

            if quantity < 0:
                raise ValueError(f"Negative quantity at {path}:{line_number} is not allowed.")

            counter[(order_id, sku)] += quantity
    return counter


def reconcile(expected: Counter[Tuple[str, str]], scanned: Counter[Tuple[str, str]]) -> List[ReconciliationRow]:
    rows: List[ReconciliationRow] = []
    for key in sorted(set(expected) | set(scanned)):
        rows.append(
            ReconciliationRow.from_counts(
                key,
                expected=expected.get(key, 0),
                scanned=scanned.get(key, 0),
            )
        )
    return rows


def render_table(rows: List[ReconciliationRow]) -> str:
    headers = [
        "Order ID",
        "SKU",
        "Expected",
        "Scanned",
        "Matched",
        "Short",
        "Overage",
    ]
    data = [
        [
            row.order_id,
            row.sku,
            str(row.expected),
            str(row.scanned),
            str(row.matched),
            str(row.short),
            str(row.overage),
        ]
        for row in rows
    ]

    totals = [
        "TOTAL",
        "",
        str(sum(row.expected for row in rows)),
        str(sum(row.scanned for row in rows)),
        str(sum(row.matched for row in rows)),
        str(sum(row.short for row in rows)),
        str(sum(row.overage for row in rows)),
    ]
    data.append(totals)

    column_widths = [len(header) for header in headers]
    for row in data:
        for idx, cell in enumerate(row):
            column_widths[idx] = max(column_widths[idx], len(cell))

    def format_row(row_values: List[str]) -> str:
        return " | ".join(cell.ljust(column_widths[idx]) for idx, cell in enumerate(row_values))

    divider = "-+-".join("-" * width for width in column_widths)
    lines = [format_row(headers), divider]
    for row in data:
        lines.append(format_row(row))
    return "\n".join(lines)


def export_results(path: Path, rows: List[ReconciliationRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = ["order_id", "sku", "expected", "scanned", "matched", "short", "overage"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    row.order_id,
                    row.sku,
                    row.expected,
                    row.scanned,
                    row.matched,
                    row.short,
                    row.overage,
                ]
            )
        writer.writerow(
            [
                "TOTAL",
                "",
                sum(row.expected for row in rows),
                sum(row.scanned for row in rows),
                sum(row.matched for row in rows),
                sum(row.short for row in rows),
                sum(row.overage for row in rows),
            ]
        )

    markdown_path = path.with_suffix(".md")
    with markdown_path.open("w", encoding="utf-8") as handle:
        headers_line = " | ".join(h.title() for h in headers)
        separator_line = " | ".join(["---"] * len(headers))
        handle.write(f"{headers_line}\n")
        handle.write(f"{separator_line}\n")
        for row in rows:
            handle.write(
                " | ".join(
                    [
                        row.order_id,
                        row.sku,
                        str(row.expected),
                        str(row.scanned),
                        str(row.matched),
                        str(row.short),
                        str(row.overage),
                    ]
                )
                + "\n"
            )
        handle.write(
            " | ".join(
                [
                    "TOTAL",
                    "",
                    str(sum(row.expected for row in rows)),
                    str(sum(row.scanned for row in rows)),
                    str(sum(row.matched for row in rows)),
                    str(sum(row.short for row in rows)),
                    str(sum(row.overage for row in rows)),
                ]
            )
        )


def main(argv: Iterable[str]) -> int:
    args = parse_arguments(argv)

    try:
        expected_counts = load_manifest(Path(args.expected))
        scanned_counts = load_manifest(Path(args.scanned))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rows = reconcile(expected_counts, scanned_counts)
    table = render_table(rows)
    print(table)

    if args.export:
        try:
            export_results(Path(args.export), rows)
        except OSError as exc:
            print(f"Failed to export results: {exc}", file=sys.stderr)
            return 1

    has_discrepancy = any(row.short > 0 or row.overage > 0 for row in rows)
    return 0 if not has_discrepancy else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
