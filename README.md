# Personal Toolbelt

A grab bag of small, task-focused scripts that I use to speed up repetitive work. Each
script is intentionally simple so that it can be tweaked quickly for one-off jobs.

## Contents

### `mass_print.py`
Automates batch printing of PDF files from a specified directory on Windows.

* **Configure** `PDF_FOLDER` with the directory that holds the PDFs.
* Keeps a `_printed.log` file so re-runs skip documents that already printed.
* Adjustable `DELAY_SECONDS` between jobs and `MAX_RETRIES` for flaky spoolers.
* Set `DRY_RUN = True` to verify file discovery without sending print jobs.

> ℹ️ Uses `os.startfile(..., "print")`, so it depends on the default PDF handler in
> Windows and should be launched from a Windows environment.

### `qrgenerator.py`
Quickly build a high-error-correction QR code using the `qrcode` Python package.

* Update the `data` string with the URL or text you want to encode.
* Adjust `box_size`, `border`, or `error_correction` to tweak output quality.
* Saves the generated PNG to `file_path`; point it at your preferred destination.

### `vendor_invoice_sorter.py`
Rules-driven sorter that shuttles PDF and Excel invoices into vendor folders.

* Point `SOURCE_DIR` at the directory that holds newly downloaded invoices, or
  supply an override via `--source /path/to/invoices` when running the script.
* Populate `VENDOR_RULES` with `pattern: destination` mappings. Patterns are
  evaluated in order; glob patterns (default) match via `fnmatch` and regex
  patterns begin with `"re:"` and are matched case-insensitively.
* Destination folders are created automatically beneath the source directory,
  with safeguards that prevent `..` escapes outside that base path.
* Unmatched files are reported to stdout so you can extend `VENDOR_RULES`.
* Preview the planned moves with:

  ```bash
  python vendor_invoice_sorter.py --dry-run --source ~/Downloads
  ```

  Omit `--dry-run` to actually relocate the files once the preview looks right.

Dependencies are tracked in `requirements.txt`. It currently installs
[`qrcode[pil]`](https://pypi.org/project/qrcode/) for `qrgenerator.py`; `mass_print.py`
only needs the Python standard library on Windows. Install everything with:

```bash
pip install -r requirements.txt
```

Run `qrgenerator.py` with:

```bash
python qrgenerator.py
```

The script will create the image and print the saved path so you can open it right
away.

## Getting Started

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   This pulls in `qrcode[pil]` (version 7.4 or newer) for QR generation. If
   reproducibility is critical for your workflow, feel free to pin an exact version in
   `requirements.txt`.

3. Tweak the script constants for your current task and run the script with Python 3.9+
   (Windows required for `mass_print.py`).

## Notes

* Treat these scripts as templates—copy, rename, and customize them for the job at
  hand.
* Add new helpers to the repository as you build them so everything stays in one place.

Happy hacking!
