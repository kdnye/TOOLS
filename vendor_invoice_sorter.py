"""Sort vendor invoices into vendor-specific directories.

This script scans the configured ``SOURCE_DIR`` for invoice files, determines the
vendor for each invoice based on a simple filename convention, and moves the
invoice into a vendor-specific subdirectory under ``DESTINATION_ROOT``.  The
script supports a ``--dry-run`` flag so you can preview what would happen without
actually touching the filesystem.
"""
from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

SOURCE_DIR = Path("SOURCE_DIR")
DESTINATION_ROOT = Path("DESTINATION_ROOT")

VENDOR_PATTERN = re.compile(r"^(?P<vendor>[A-Za-z0-9]+)[_-].+")


@dataclass(frozen=True)
class Invoice:
    path: Path

    @property
    def vendor(self) -> str:
        """Return the vendor inferred from the filename.

        Vendors are expected to prefix the filename separated by an underscore or
        hyphen, e.g. ``acme-2024-01.pdf``.  If no vendor marker is present, the
        invoice is categorized under ``unknown``.
        """

        match = VENDOR_PATTERN.match(self.path.name)
        if not match:
            return "unknown"
        return match.group("vendor").lower()


def iter_invoices(source_dir: Path) -> Iterator[Invoice]:
    """Yield invoices discovered in ``source_dir``."""

    yield from (Invoice(path) for path in sorted(source_dir.glob("*.pdf")))


def move_invoice(invoice: Invoice, destination: Path, dry_run: bool) -> None:
    """Move ``invoice`` into ``destination`` when not running a dry-run.

    The destination directory is only created when ``dry_run`` is ``False`` so
    that preview runs do not leave any traces on disk.  In dry-run mode the
    function simply prints the action that *would* be performed.
    """

    destination = destination / invoice.path.name

    if dry_run:
        print(f"[DRY-RUN] Would move {invoice.path} -> {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(invoice.path), str(destination))
    print(f"Moved {invoice.path} -> {destination}")


def sort_invoices(
    source_dir: Path = SOURCE_DIR,
    destination_root: Path = DESTINATION_ROOT,
    dry_run: bool = False,
) -> None:
    """Sort invoices discovered in ``source_dir``."""

    if not source_dir.exists():
        print(f"Source directory {source_dir} does not exist; nothing to do.")
        return

    for invoice in iter_invoices(source_dir):
        vendor_dir = destination_root / invoice.vendor
        move_invoice(invoice, vendor_dir, dry_run=dry_run)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_DIR,
        help="Directory containing invoice files (default: SOURCE_DIR).",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=DESTINATION_ROOT,
        help="Directory to receive sorted invoices (default: DESTINATION_ROOT).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without moving files or creating directories.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    sort_invoices(args.source, args.destination, dry_run=args.dry_run)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
