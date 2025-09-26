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
[`qrcode[pil]`](https://pypi.org/project/qrcode/) for `qrgenerator.py`; `mass_print.py`
only needs the Python standard library on Windows. Install everything with:

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

### `inventory_reorder_report.py`
Highlight products that have dipped below their reorder point in an inventory
snapshot CSV.

* **Input expectations:** the CSV must provide at least `Item`, `On Hand`, and
  `Reorder Point` columns (case-insensitive; spaces/underscores are ignored when
  matching headers). Optional columns such as `Vendor`, `Category`, `SKU`, or
  `Description` are displayed when available.
* Quantities must be numeric and zero-or-greater. Rows missing any required
  values are skipped with a validation message so you can correct the source
  data.
* You can narrow the report with `--vendor` and/or `--category` filters. Provide
  the flags multiple times to include several values.

Typical runs look like:

```bash
python inventory_reorder_report.py inventory_snapshot.csv

python inventory_reorder_report.py inventory_snapshot.csv \
  --vendor "Acme Co" --vendor "Widget Works" \
  --category "Networking" \
  --export reorder.md
```

The script prints a severity-sorted table showing on-hand quantities, reorder
points, and computed shortages. When `--export` is supplied the table is written
to CSV (`.csv`) or Markdown (`.md`/`.markdown`) so you can hand it to purchasing
or paste it into documentation.

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
