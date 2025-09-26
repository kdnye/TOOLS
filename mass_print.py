import os, time

# >>> PATH TO FILE <<<
PDF_FOLDER = r"C:\Users\dalexander\Downloads\SS  DC ASSH-20250925T152902Z-1-001\SS  DC ASSH"

DELAY_SECONDS = 7          # pause between jobs (increase if spooler/printer is slow)
MAX_RETRIES = 2            # retry per file if the print verb throws
LOG_FILE = os.path.join(PDF_FOLDER, "_printed.log")
DRY_RUN = False            # set True to test without actually printing

# Load already-printed filenames (resume-safe)
printed = set()
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        printed = {line.strip() for line in f if line.strip()}

# Collect PDFs (top-level only) and sort
pdfs = sorted(
    f for f in os.listdir(PDF_FOLDER)
    if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(PDF_FOLDER, f))
)

total = len(pdfs)
print(f"Found {total} PDFs in: {PDF_FOLDER}")

def print_once(path: str):
    os.startfile(path, "print")  # uses the default PDF app’s print verb

for idx, name in enumerate(pdfs, 1):
    if name in printed:
        print(f"[skip] {name} (already logged)")
        continue

    full = os.path.join(PDF_FOLDER, name)
    print(f"[{idx}/{total}] Printing: {full}")

    if DRY_RUN:
        time.sleep(0.2)
        continue

    attempt = 0
    while True:
        try:
            attempt += 1
            print_once(full)
            time.sleep(DELAY_SECONDS)  # give spooler time
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(name + "\n")
            break
        except OSError as e:
            print(f"[warn] Attempt {attempt} failed for {name}: {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(DELAY_SECONDS * 2)
                continue
            print(f"[error] Skipping {name} after {MAX_RETRIES} retries.")
            break

print("Done.")
