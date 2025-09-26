"""Summarise timesheet CSV data by ISO week and project/client.

This module exposes a CLI that accepts a path to a CSV file and the names
of the columns that represent the entry date, the project/client name, and
the recorded hours. It normalises the date values into ISO calendar weeks,
aggregates total hours per project, and prints a tabular report. Optionally,
the report can be exported to a CSV or Markdown file via ``--export``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


# Supported fallback date formats when the standard ISO format fails.
_DATE_FORMATS: Tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
)


@dataclass(frozen=True)
class SummaryRow:
    """Container for summarised hours for a project within an ISO week."""

    iso_week: str
    project: str
    hours: float


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Summarise a timesheet CSV file by ISO week and project/client. "
            "By default, the script expects columns named 'Date', 'Project', "
            "and 'Hours'."
        )
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the timesheet CSV file.",
    )
    parser.add_argument(
        "--columns",
        nargs=3,
        metavar=("DATE_COLUMN", "PROJECT_COLUMN", "HOURS_COLUMN"),
        default=("Date", "Project", "Hours"),
        help=(
            "Names of the columns to interpret as the entry date, project "
            "or client, and hours respectively."
        ),
    )
    parser.add_argument(
        "--export",
        type=Path,
        help=(
            "Optional path for exporting the summary. The extension "
            "determines the format (.csv or .md)."
        ),
    )
    return parser.parse_args(argv)


def _parse_date(raw_value: str, row_number: int) -> date:
    """Normalise incoming date strings into :class:`datetime.date` objects."""

    value = (raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: missing date value")

    # Attempt to parse using ISO formats first.
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Row {row_number}: unsupported date format '{value}'")


def _parse_hours(raw_value: str, row_number: int) -> float:
    """Ensure the hours value is numeric and non-negative."""

    value = (raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: missing hours value")

    try:
        hours = float(value)
    except ValueError as exc:  # pragma: no cover - informative error path
        raise ValueError(f"Row {row_number}: invalid hours value '{value}'") from exc

    if hours < 0:
        raise ValueError(f"Row {row_number}: negative hours value '{hours}'")

    return hours


def _load_timesheet(
    csv_path: Path,
    column_names: Sequence[str],
) -> Tuple[List[SummaryRow], List[str]]:
    """Read and aggregate the CSV data.

    Returns a tuple containing the summary rows and any validation messages
    emitted during parsing.
    """

    date_col, project_col, hours_col = column_names
    totals: Dict[Tuple[int, int, str], float] = defaultdict(float)
    messages: List[str] = []

    if not csv_path.exists():
        raise FileNotFoundError(f"Timesheet file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)

        missing_columns = {
            column
            for column in (date_col, project_col, hours_col)
            if column not in reader.fieldnames if reader.fieldnames
        }
        if missing_columns:
            raise KeyError(
                "Timesheet CSV is missing expected columns: "
                + ", ".join(sorted(missing_columns))
            )

        for index, row in enumerate(reader, start=2):  # header is row 1
            try:
                entry_date = _parse_date(row.get(date_col, ""), index)
                hours = _parse_hours(row.get(hours_col, ""), index)
            except ValueError as err:
                messages.append(str(err))
                continue

            project = (row.get(project_col) or "Unspecified").strip() or "Unspecified"
            iso_year, iso_week, _ = entry_date.isocalendar()
            key = (iso_year, iso_week, project)
            totals[key] += hours

    summary_rows = [
        SummaryRow(iso_week=f"{year}-W{week:02d}", project=project, hours=hours)
        for (year, week, project), hours in totals.items()
    ]

    summary_rows.sort(key=lambda item: (item.iso_week, item.project.lower()))
    return summary_rows, messages


def _format_table(rows: Iterable[SummaryRow]) -> str:
    """Render a plain-text table suitable for terminal output."""

    headers = ("ISO Week", "Project/Client", "Total Hours")
    data = [headers]
    for row in rows:
        data.append((row.iso_week, row.project, f"{row.hours:.2f}"))

    widths = [max(len(str(item[i])) for item in data) for i in range(len(headers))]

    lines = []
    header_line = " | ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers)))
    separator = "-+-".join("-" * widths[i] for i in range(len(headers)))
    lines.append(header_line)
    lines.append(separator)

    for row in data[1:]:
        lines.append(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))

    return "\n".join(lines)


def _export_summary(path: Path, rows: Iterable[SummaryRow]) -> None:
    """Export the summary rows to CSV or Markdown based on file extension."""

    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ISO Week", "Project/Client", "Total Hours"])
            for row in rows:
                writer.writerow([row.iso_week, row.project, f"{row.hours:.2f}"])
    elif suffix in {".md", ".markdown"}:
        with path.open("w", encoding="utf-8") as handle:
            handle.write("| ISO Week | Project/Client | Total Hours |\n")
            handle.write("|----------|----------------|-------------|\n")
            for row in rows:
                handle.write(
                    f"| {row.iso_week} | {row.project} | {row.hours:.2f} |\n"
                )
    else:
        raise ValueError(
            "Unsupported export format. Use a .csv or .md/.markdown extension."
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the CLI."""

    args = parse_args(argv or sys.argv[1:])

    try:
        summary_rows, messages = _load_timesheet(args.csv_path, args.columns)
    except (FileNotFoundError, KeyError) as err:
        print(err, file=sys.stderr)
        return 1

    if not summary_rows:
        print("No valid rows were found in the provided CSV file.")
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
