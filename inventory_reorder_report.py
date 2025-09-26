"""Generate a reorder report from an inventory snapshot CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


_ITEM_KEY = "item"
_ON_HAND_KEY = "onhand"
_REORDER_POINT_KEY = "reorderpoint"

_REQUIRED_COLUMNS = {_ITEM_KEY, _ON_HAND_KEY, _REORDER_POINT_KEY}
_OPTIONAL_COLUMNS = {"vendor", "category", "sku", "description"}


@dataclass(frozen=True)
class InventoryRecord:
    """Typed representation of a row in the inventory snapshot."""

    item: str
    on_hand: float
    reorder_point: float
    vendor: str | None = None
    category: str | None = None
    sku: str | None = None
    description: str | None = None

    @property
    def shortage(self) -> float:
        return max(self.reorder_point - self.on_hand, 0.0)

    @property
    def severity_ratio(self) -> float:
        if self.shortage <= 0:
            return 0.0
        if self.reorder_point == 0:
            return float("inf")
        return self.shortage / self.reorder_point


@dataclass(frozen=True)
class SummaryRow:
    """Row for the rendered output table."""

    item: str
    vendor: str
    category: str
    on_hand: float
    reorder_point: float
    shortage: float
    severity_ratio: float


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments for the reorder report."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect an inventory snapshot CSV and flag products where the "
            "on-hand quantity is at or below the reorder point."
        )
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the inventory snapshot CSV file.",
    )
    parser.add_argument(
        "--vendor",
        dest="vendors",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Optional vendor filter. Provide multiple times to include several "
            "vendors. Matching is case-insensitive."
        ),
    )
    parser.add_argument(
        "--category",
        dest="categories",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Optional category filter. Provide multiple times to include several "
            "categories. Matching is case-insensitive."
        ),
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Optional path for exporting the summary as CSV or Markdown.",
    )
    return parser.parse_args(argv)


def _normalise_header(column: str) -> str:
    cleaned = column.strip().lower()
    for char in (" ", "_"):
        cleaned = cleaned.replace(char, "")
    return cleaned


def _format_optional(value: str | None) -> str:
    return value if value else "—"


def _format_quantity(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.2f}"


def _load_inventory(csv_path: Path) -> Tuple[List[InventoryRecord], List[str]]:
    """Load the CSV file and return parsed inventory records."""

    records: List[InventoryRecord] = []
    messages: List[str] = []

    if not csv_path.exists():
        raise FileNotFoundError(f"Inventory file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        header_lookup = { _normalise_header(name): name for name in fieldnames }

        missing_columns = _REQUIRED_COLUMNS - header_lookup.keys()
        if missing_columns:
            readable = ", ".join(sorted(missing_columns))
            raise KeyError(
                "Inventory CSV is missing required column(s): " + readable
            )

        for index, row in enumerate(reader, start=2):
            item_name = (row.get(header_lookup[_ITEM_KEY], "") or "").strip()
            if not item_name:
                messages.append(f"Row {index}: missing item identifier")
                continue

            try:
                on_hand = _parse_quantity(
                    row.get(header_lookup[_ON_HAND_KEY], ""), index, "on hand"
                )
                reorder_point = _parse_quantity(
                    row.get(header_lookup[_REORDER_POINT_KEY], ""),
                    index,
                    "reorder point",
                )
            except ValueError as err:
                messages.append(str(err))
                continue

            optional_values = {
                key: (row.get(header_lookup[key], "") or "").strip() or None
                for key in _OPTIONAL_COLUMNS
                if key in header_lookup
            }

            record = InventoryRecord(
                item=item_name,
                on_hand=on_hand,
                reorder_point=reorder_point,
                vendor=optional_values.get("vendor"),
                category=optional_values.get("category"),
                sku=optional_values.get("sku"),
                description=optional_values.get("description"),
            )
            records.append(record)

    return records, messages


def _parse_quantity(raw_value: str | None, row_number: int, label: str) -> float:
    value = (raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: missing {label} value")

    try:
        quantity = float(value)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: invalid {label} value '{value}'") from exc

    if quantity < 0:
        raise ValueError(
            f"Row {row_number}: negative {label} value '{quantity}'"
        )
    return quantity


def _filter_records(
    records: Iterable[InventoryRecord],
    vendors: Sequence[str],
    categories: Sequence[str],
) -> List[InventoryRecord]:
    vendor_set = {vendor.lower() for vendor in vendors if vendor}
    category_set = {category.lower() for category in categories if category}

    filtered: List[InventoryRecord] = []
    for record in records:
        if vendor_set:
            if not record.vendor or record.vendor.lower() not in vendor_set:
                continue
        if category_set:
            if not record.category or record.category.lower() not in category_set:
                continue
        filtered.append(record)
    return filtered


def _build_summary(records: Iterable[InventoryRecord]) -> List[SummaryRow]:
    summary_rows: List[SummaryRow] = []
    for record in records:
        if record.shortage <= 0:
            continue
        summary_rows.append(
            SummaryRow(
                item=record.item,
                vendor=_format_optional(record.vendor),
                category=_format_optional(record.category),
                on_hand=record.on_hand,
                reorder_point=record.reorder_point,
                shortage=record.shortage,
                severity_ratio=record.severity_ratio,
            )
        )

    summary_rows.sort(
        key=lambda row: (
            -row.severity_ratio,
            -row.shortage,
            row.item.lower(),
        )
    )
    return summary_rows


def _format_table(rows: Sequence[SummaryRow]) -> str:
    headers = (
        "Item",
        "Vendor",
        "Category",
        "On Hand",
        "Reorder Point",
        "Shortage",
        "Severity",
    )

    data = [headers]
    for row in rows:
        severity_display = (
            "∞" if row.severity_ratio == float("inf") else f"{row.severity_ratio * 100:.0f}%"
        )
        data.append(
            (
                row.item,
                row.vendor,
                row.category,
                _format_quantity(row.on_hand),
                _format_quantity(row.reorder_point),
                _format_quantity(row.shortage),
                severity_display,
            )
        )

    widths = [max(len(str(item[i])) for item in data) for i in range(len(headers))]

    lines: List[str] = []
    header_line = " | ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers)))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))
    lines.append(header_line)
    lines.append(separator)

    for row in data[1:]:
        lines.append(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))

    return "\n".join(lines)


def _export_summary(path: Path, rows: Sequence[SummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    headers = (
        "Item",
        "Vendor",
        "Category",
        "On Hand",
        "Reorder Point",
        "Shortage",
        "Severity",
    )

    if suffix == ".csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows:
                severity_display = (
                    "inf" if row.severity_ratio == float("inf") else f"{row.severity_ratio:.4f}"
                )
                writer.writerow(
                    [
                        row.item,
                        row.vendor,
                        row.category,
                        _format_quantity(row.on_hand),
                        _format_quantity(row.reorder_point),
                        _format_quantity(row.shortage),
                        severity_display,
                    ]
                )
    elif suffix in {".md", ".markdown"}:
        with path.open("w", encoding="utf-8") as handle:
            handle.write("| Item | Vendor | Category | On Hand | Reorder Point | Shortage | Severity |\n")
            handle.write("|------|--------|----------|---------|---------------|----------|----------|\n")
            for row in rows:
                severity_display = (
                    "∞" if row.severity_ratio == float("inf") else f"{row.severity_ratio * 100:.0f}%"
                )
                handle.write(
                    "| {item} | {vendor} | {category} | {on_hand} | {reorder} | {shortage} | {severity} |\n".format(
                        item=row.item,
                        vendor=row.vendor,
                        category=row.category,
                        on_hand=_format_quantity(row.on_hand),
                        reorder=_format_quantity(row.reorder_point),
                        shortage=_format_quantity(row.shortage),
                        severity=severity_display,
                    )
                )
    else:
        raise ValueError(
            "Unsupported export format. Use a .csv or .md/.markdown extension."
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        records, messages = _load_inventory(args.csv_path)
    except (FileNotFoundError, KeyError) as err:
        print(err, file=sys.stderr)
        return 1

    filtered_records = _filter_records(records, args.vendors, args.categories)
    summary_rows = _build_summary(filtered_records)

    if not summary_rows:
        print("No products met the reorder criteria.")
    else:
        print(_format_table(summary_rows))

    if args.export:
        try:
            _export_summary(args.export, summary_rows)
        except ValueError as err:
            print(err, file=sys.stderr)
            return 1

    if messages:
        for message in messages:
            print(message, file=sys.stderr)
        print(
            f"Skipped {len(messages)} row(s) due to validation errors.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
