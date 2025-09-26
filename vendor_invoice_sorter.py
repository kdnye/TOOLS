"""Utilities for sorting vendor invoices into vendor-specific folders.

This module looks for PDF or Excel files inside ``SOURCE_DIR`` and moves each
file into the directory specified by the first matching rule from
``VENDOR_RULES``.  A rule is expressed as a mapping of a filename pattern to a
destination folder.  Patterns are evaluated in the order they are defined and
may be either ``fnmatch`` glob patterns (default) or regular expressions when
prefixed with ``"re:"``.  The optional ``--dry-run`` flag can be used to log
the planned moves without modifying the filesystem.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
from pathlib import Path
from typing import Iterable

# Directory that contains invoice files to classify.
SOURCE_DIR = Path("/path/to/invoice/source")

# Mapping of pattern -> destination directory (relative to SOURCE_DIR).
#
# Patterns prefixed with "re:" are treated as case-insensitive regular
# expressions.  All other patterns are interpreted using fnmatch-style glob
# semantics.  Destination folders are created on demand.
VENDOR_RULES = {
    # "*.acme_invoice.pdf": "AcmeCorp",
    # "re:.*contoso.*\\.(pdf|xlsx?)$": "Contoso",
}


INVOICE_EXTENSIONS = {".pdf", ".xls", ".xlsx"}


def iter_invoices(directory: Path) -> Iterable[Path]:
    """Yield supported invoice files inside *directory* (non-recursively)."""

    for candidate in directory.iterdir():
        if candidate.is_file() and candidate.suffix.lower() in INVOICE_EXTENSIONS:
            yield candidate


def evaluate_rules(filename: str) -> tuple[str, Path] | tuple[None, None]:
    """Return the first matching destination for *filename*.

    The function respects the insertion order of ``VENDOR_RULES``.
    """

    for pattern, destination in VENDOR_RULES.items():
        if pattern.startswith("re:"):
            regex = pattern[3:]
            if re.search(regex, filename, re.IGNORECASE):
                return pattern, Path(destination)
        else:
            if fnmatch.fnmatch(filename, pattern):
                return pattern, Path(destination)

    return None, None


def move_invoice(invoice: Path, destination: Path, dry_run: bool = False) -> None:
    """Move *invoice* into *destination* (relative to SOURCE_DIR)."""

    target_dir = SOURCE_DIR / destination
    target_path = target_dir / invoice.name

    if dry_run:
        print(f"[DRY-RUN] Would move '{invoice}' -> '{target_path}'")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Moving '{invoice}' -> '{target_path}'")
    shutil.move(str(invoice), str(target_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sort vendor invoices by rule")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned moves without touching the filesystem.",
    )
    args = parser.parse_args()

    if not SOURCE_DIR.exists():
        raise SystemExit(f"SOURCE_DIR does not exist: {SOURCE_DIR}")

    unmatched_files = []

    for invoice in iter_invoices(SOURCE_DIR):
        pattern, destination = evaluate_rules(invoice.name)
        if destination is None:
            unmatched_files.append(invoice)
            continue

        move_invoice(invoice, destination, dry_run=args.dry_run)

    if unmatched_files:
        print("\nUnmatched invoices:")
        for invoice in unmatched_files:
            print(f" - {invoice}")


if __name__ == "__main__":
    main()
