# BBTS Tool 01: Traditional PDF to Simplified TXT

This tool runs a full pipeline in one script:

1. OCR a Traditional Chinese PDF
2. Export merged Traditional text (`merged_corrected.txt`)
3. Convert merged text to Simplified Chinese (`merged_simplified.txt`)
4. Export page stats and low-confidence report

## Script

- `trad_pdf_to_simp.py`

## Local run

```bash
python -m pip install -r BBTS/tools/requirements.txt
python BBTS/tools/trad_pdf_to_simp.py --input-pdf /path/to/file.pdf --out-dir out
```

Useful options:

- `--reading-order rtl_tb` for vertical Traditional layout (top-to-bottom, right-to-left)
- `--start-page 1 --end-page 10` to process a range
- `--dpi 300` to control render resolution
- `--save-raw-per-page` to export uncorrected page OCR text

## Cloud run (GitHub Actions)

Use workflow: `.github/workflows/trad-pdf-to-simp.yml`

Inputs:

- `pdf_url` (required): a public direct URL to a PDF file
- `dpi`
- `reading_order`
- `start_page`
- `end_page`
- `save_raw_per_page`

After run completes, download artifact:

- `trad-pdf-to-simp-output`

## Web upload entry

Use `BBTS/upload.html` as a browser entry point.

What it does:

1. Uploads your local PDF to `BBTS/uploads/...` in the repo
2. Triggers `.github/workflows/trad-pdf-to-simp-from-repo.yml`
3. You download results from Actions artifact `trad-pdf-to-simp-output`
