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

### `csv_mail_merge.py`
Generate individualized text drafts from a CSV file and a simple text template.

* Each CSV row must include an `id` column that uniquely identifies the record.
* Template placeholders use Python `str.format` syntax (e.g., `{name}`, `{address}`).
* Empty or missing fields are reported and skipped so you can fill the gaps.

Run it with:

```bash
python csv_mail_merge.py --csv contacts.csv --template letter.txt --output-dir out/
```

`contacts.csv` should include columns for every placeholder used in `letter.txt`. The
script writes one text file per row to `out/` named after the `id` value
(`out/<id>.txt`) and prints a summary detailing generated drafts and any rows skipped
for missing data.

Dependencies are tracked in `requirements.txt`. It currently installs
[`qrcode[pil]`](https://pypi.org/project/qrcode/) and
[`Pillow`](https://pypi.org/project/Pillow/) for the QR/label tooling;
`mass_print.py` only needs the Python standard library on Windows. Install
everything with:

```bash
pip install -r requirements.txt
```

### `timesheet_weekly_summary.py`
Roll up CSV-based timesheet entries into ISO calendar week buckets per
project/client.

* **Input expectations:** the CSV must contain one row per entry with columns for
  the entry date, project/client label, and recorded hours. By default the script
  looks for `Date`, `Project`, and `Hours`, but you can point it at custom names
  with `--columns DATE PROJECT HOURS`.
* Dates are normalised using common ISO and numeric formats (e.g. `2024-04-03`,
  `03/04/2024`). Invalid or missing dates/hours are skipped and reported to
  `stderr` so you can fix the original file.
* Hours must be numeric and non-negative. Rows that do not meet that criteria are
  ignored for the summary and counted in the validation output.

Run the tool with:

```bash
python timesheet_weekly_summary.py timesheet.csv \
  --columns Date Project Hours \
  --export summary.md
```

`--export` is optional; when supplied the extension controls the output format
(`.csv` or `.md`). The terminal output always prints a plain-text table so you can
spot-check totals quickly.

Run `qrgenerator.py` with:

```bash
python qrgenerator.py
```

The script will create the image and print the saved path so you can open it right
away.

### `pallet_label_batcher.py`
Generate thermal-printer-friendly pallet labels that combine a QR code with text
metadata sourced from a CSV file.

* Each CSV row must include a `pallet_id` column (or a legacy `pallet` column,
  which the tool transparently maps to `pallet_id`); additional columns such as
  `destination` or `contents` are inserted into the label when referenced in the
  default template.
* Produces both PNG and PDF versions sized for 4x6" printers by default. Adjust
  clarity or sizing with `--dpi` (e.g., `--dpi 300` for higher-resolution
  printers).
* Override the default layout with `--template path/to/layout.json`. The template
  file is JSON with three optional sections:

  ```json
  {
    "label": {"width_in": 4, "height_in": 6},
    "qr": {
      "position": [900, 120],
      "size_in": 2.25,
      "box_size": 12,
      "border": 4
    },
    "text_blocks": [
      {
        "text": "Pallet: {pallet_id}",
        "position": [80, 80],
        "font_size": 72
      },
      {
        "text": "Dest: {destination}\nNotes: {contents}",
        "position": [80, 220],
        "font_size": 42,
        "max_width": 650
      }
    ]
  }
  ```

Run the batcher with:

```bash
python pallet_label_batcher.py --csv pallets.csv --output-dir labels/ --dpi 300
```

Each pallet produces `labels/<pallet_id>.png` and `labels/<pallet_id>.pdf`.

## Getting Started

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   This pulls in `qrcode[pil]` (version 7.4 or newer) and Pillow for QR/label
   generation. If reproducibility is critical for your workflow, feel free to pin an
   exact version in `requirements.txt`.

3. Tweak the script constants for your current task and run the script with Python 3.9+
   (Windows required for `mass_print.py`).

## Notes

* Treat these scripts as templates—copy, rename, and customize them for the job at
  hand.
* Add new helpers to the repository as you build them so everything stays in one place.

Happy hacking!
