"""Rules-driven utilities for sorting vendor invoices.

This module looks for PDF or Excel files inside ``SOURCE_DIR`` and moves each
file into the directory specified by the first matching rule from
``VENDOR_RULES``. A rule is expressed as a mapping of a filename pattern to a
destination folder. Patterns are evaluated in insertion order and may be either
``fnmatch`` glob patterns (default) or regular expressions when prefixed with
``"re:"``. Use the ``--dry-run`` CLI flag to preview moves without touching the
filesystem. ``--source`` lets you point the sorter at a different directory
without editing the module.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

# Directory that contains invoice files to classify.
SOURCE_DIR = Path("/path/to/invoice/source")

# Mapping of pattern -> destination directory (relative to SOURCE_DIR).
#
# Patterns prefixed with "re:" are treated as case-insensitive regular
# expressions. All other patterns are interpreted using fnmatch-style glob
# semantics. Destination folders are created on demand.
VENDOR_RULES = {
    # "*.acme_invoice.pdf": "AcmeCorp",
    # "re:.*contoso.*\\.(pdf|xlsx?)$": "Contoso",
}


INVOICE_EXTENSIONS = {".pdf", ".xls", ".xlsx"}


@dataclass(frozen=True)
class CompiledRule:
    """Representation of a normalized vendor rule."""

    pattern: str
    destination: Path
    matcher: Callable[[str], bool]


def iter_invoices(directory: Path) -> Iterator[Path]:
    """Yield supported invoice files inside *directory* (non-recursively)."""

    for candidate in sorted(directory.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in INVOICE_EXTENSIONS:
            yield candidate


def compile_rules(rules: dict[str, str]) -> Sequence[CompiledRule]:
    """Normalize ``rules`` into ready-to-evaluate callables."""

    compiled: list[CompiledRule] = []
    for pattern, destination in rules.items():
        dest_path = Path(destination)
        if pattern.startswith("re:"):
            regex = re.compile(pattern[3:], re.IGNORECASE)
            compiled.append(
                CompiledRule(
                    pattern=pattern,
                    destination=dest_path,
                    matcher=regex.search,
                )
            )
        else:
            compiled.append(
                CompiledRule(
                    pattern=pattern,
                    destination=dest_path,
                    matcher=lambda filename, p=pattern: fnmatch.fnmatch(filename, p),
                )
            )
    return compiled


def evaluate_rules(filename: str, rules: Sequence[CompiledRule]) -> tuple[str, Path] | tuple[None, None]:
    """Return the first matching destination for *filename* from ``rules``."""

    for rule in rules:
        if rule.matcher(filename):
            return rule.pattern, rule.destination
    return None, None


def ensure_within_base(base_dir: Path, candidate: Path) -> Path:
    """Return ``candidate`` resolved against ``base_dir`` while enforcing bounds."""

    base_dir = base_dir.resolve()
    target = (base_dir / candidate).resolve()
    if target == base_dir:
        return target

    try:
        target.relative_to(base_dir)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"Destination '{candidate}' escapes SOURCE_DIR '{base_dir}'."
        ) from exc
    return target


def move_invoice(
    invoice: Path,
    base_dir: Path,
    destination: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Move *invoice* into *destination* relative to ``base_dir``."""

    target_dir = ensure_within_base(base_dir, destination)
    target_path = target_dir / invoice.name

    if dry_run:
        print(f"[DRY-RUN] Would move '{invoice.name}' -> '{target_path}'")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Moving '{invoice.name}' -> '{target_path}'")
    shutil.move(str(invoice), str(target_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sort vendor invoices by rule")
    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_DIR,
        help=(
            "Directory that contains newly downloaded invoices. Defaults to "
            "the SOURCE_DIR constant inside vendor_invoice_sorter.py."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned moves without touching the filesystem.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_dir = args.source.expanduser().resolve()
    if not source_dir.exists():
        raise SystemExit(f"SOURCE_DIR does not exist: {source_dir}")

    compiled_rules = compile_rules(VENDOR_RULES)
    if not compiled_rules:
        print(
            "No VENDOR_RULES configured. Add pattern -> destination mappings before running."
        )
        return

    unmatched_files: list[Path] = []

    for invoice in iter_invoices(source_dir):
        pattern, destination = evaluate_rules(invoice.name, compiled_rules)
        if destination is None:
            unmatched_files.append(invoice)
            continue

        move_invoice(invoice, source_dir, destination, dry_run=args.dry_run)

    if unmatched_files:
        print("\nUnmatched invoices:")
        for invoice in unmatched_files:
            print(f" - {invoice.name}")


if __name__ == "__main__":
    main()
