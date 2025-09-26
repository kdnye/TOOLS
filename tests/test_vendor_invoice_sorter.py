from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vendor_invoice_sorter import move_invoice


class MoveInvoiceTests(unittest.TestCase):
    def test_dry_run_does_not_create_directories_or_move_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            invoice = base_dir / "sample.pdf"
            invoice.write_bytes(b"invoice")

            move_invoice(invoice, base_dir, Path("VendorA"), dry_run=True)

            self.assertTrue(invoice.exists(), "Dry-run should not move the invoice")
            self.assertFalse(
                (base_dir / "VendorA").exists(),
                "Dry-run should not create the destination directory",
            )

    def test_move_invoice_creates_directories_and_moves_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            invoice = base_dir / "sample.pdf"
            invoice.write_bytes(b"invoice")

            move_invoice(invoice, base_dir, Path("VendorA"), dry_run=False)

            target_dir = base_dir / "VendorA"
            target_file = target_dir / "sample.pdf"
            self.assertTrue(target_dir.is_dir(), "Destination directory should exist")
            self.assertTrue(target_file.is_file(), "Invoice should be moved to the destination")
            self.assertFalse(invoice.exists(), "Original invoice should no longer exist")


if __name__ == "__main__":
    unittest.main()
