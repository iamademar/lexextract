Here’s a multi-layered plan that goes from high-level phases down to test-driven, code-generation LLM prompts. Each “Prompt Section” builds on the previous and ends by wiring the new piece into the existing pipeline—no orphaned code. Make sure to run the tests before proceeding to the next prompt.

---

## 1. High-Level Blueprint

1. **Requirements & Environment Setup**
   • Audit existing LexExtract pipeline.
   • Pin down sample PDFs and desired transaction model.
   • Prepare dev environment (Docker, memory, system deps).

2. **PDF Type Detection**
   • Implement “is\_text\_page” vs. “is\_scanned\_page” using PyPDF2/pdfplumber.
   • Unit-test on mixed sample pages.

3. **Dependencies**
   • Add `camelot-py[cv]`, `ghostscript`/`poppler-utils`, `pdfplumber`, `pytesseract`.
   • Ensure Docker image installs system libs.
   • Smoke-test import in Python REPL.

4. **Camelot Extraction Service**
   • New module: `app/services/camelot_ocr.py`.
   • Function `extract_tables_with_camelot(pdf_path, pages, flavor) -> List[pd.DataFrame]`.
   • Handle both `lattice` and `stream`.
   • Unit-test on vector-PDF tables.

5. **Tesseract Fallback Enhancement**
   • New/extended module: `app/services/tesseract_ocr.py`.
   • Convert PDF→image (via `pdfplumber` or `pdf2image`).
   • Try `camelot.read_pdf(image_path, flavor='lattice', edge_tol=…)`.
   • If no tables, detect table regions, OCR each crop with `pytesseract`.
   • Unit-test on scanned-PDF tables.

6. **Unified OCR Pipeline**
   • Refactor `app/services/ocr.py`’s `run_ocr()`:

   1. For each page: detect type.
   2. If text → Camelot; else → Tesseract fallback.
      • Return `[{"page": n, "tables": [[…]], "full_text": str}]`.
      • Integration test end-to-end on mixed PDF.

7. **Transaction Parser**
   • Update `app/services/parser.py` to consume unified tables.
   • Map columns → `date`, `payee`, `amount`, `balance`.
   • Regex/date-helper + `Decimal`.
   • Return list of `TransactionData`.
   • Unit-test with known statements.

8. **Confidence Metrics & Logging**
   • If Camelot table too small/wide → auto-fallback and log.
   • Add log lines in both paths.
   • Test simulated low-confidence.

9. **Tests & CI**
   • Create `tests/test_camelot_ocr.py`, `tests/test_tesseract_ocr.py`, `tests/test_parser_integration.py`.
   • Add to CI, ensure system deps in container.

10. **Docs & Deployment**
    • Update `README.md`, `docker-compose.yml`.
    • Document new env vars and memory reqs.
    • Deploy to staging, monitor errors.

---

## 2. Iterative Chunks & Sub-Steps

### Chunk 1: PDF Type Detection

1. Create `app/services/pdf_utils.py`.
2. Implement `is_text_page(pdf_path, page_no)`.
3. Implement `is_scanned_page(...)` as `not is_text_page`.
4. Write `tests/test_pdf_utils.py` covering both cases.

### Chunk 2: Add Dependencies

1. Update `requirements.txt` with Python packages.
2. Modify `Dockerfile` / `docker-compose.yml` to install Ghostscript & Poppler.
3. Locally rebuild container and run `python -c "import camelot, pytesseract, pdfplumber"`.

### Chunk 3: Camelot Service

1. New file `camelot_ocr.py` with `extract_tables_with_camelot()`.
2. Support optional `flavor` param.
3. Write `tests/test_camelot_ocr.py` on vector-PDF sample.

### Chunk 4: Tesseract Fallback

1. Extend or create `tesseract_ocr.py` to convert pages → images.
2. Try Camelot on image first; if empty, crop regions & OCR via `pytesseract`.
3. Write `tests/test_tesseract_ocr.py` on scanned PDF sample.

### Chunk 5: Unified Pipeline

1. Refactor `run_ocr()` in `ocr.py` to call pdf\_utils + Camelot/Tesseract.
2. Define uniform return structure.
3. Write `tests/test_ocr_integration.py` on mixed PDF.

### Chunk 6: Transaction Parser

1. In `parser.py`, accept unified tables.
2. Map and normalize columns; build `TransactionData`.
3. Write `tests/test_parser.py` for correct parsing.

### Chunk 7: Confidence & Logging

1. Add heuristics for table quality in Camelot service.
2. On low quality, call fallback and log both.
3. Write unit tests simulating small/large tables.

### Chunk 8: CI & Documentation

1. Update `README.md` with new steps.
2. Modify CI config to install system deps.
3. Add integration test stage.

### Chunk 9: Deployment & Monitoring

1. Deploy to staging.
2. Monitor logs for OCR errors.
3. Tweak thresholds.

---

## 3. Code-Generation LLM Prompt Sections

> **Note:** each prompt assumes the codebase up to the previous prompt is already merged.

---

### Prompt Section 1: PDF Type Detection

```
Context:
  - We have a LexExtract repo with `app/services/ocr.py`.
  - We need to decide per-page whether to use Camelot (text-PDF) or Tesseract fallback (scanned-PDF).
Task:
  1. Create `app/services/pdf_utils.py`.
  2. Implement `is_text_page(pdf_path: str, page_no: int) -> bool` using pdfplumber or PyPDF2—return True if any text chars.
  3. Implement `is_scanned_page(...)` as `not is_text_page(...)`.
  4. Write unit tests in `tests/test_pdf_utils.py` covering both a text-PDF and a scanned-PDF sample.
Goal:
  - Running `pytest tests/test_pdf_utils.py` should pass.
Integration:
  - Export these functions so `run_ocr()` can import them.
```

---

### Prompt Section 2: Add Dependencies

```
Context:
  - After PDF-type detection, we’ll need Camelot, pdfplumber, pytesseract and system libs.
Task:
  1. Add to `requirements.txt`:
       camelot-py[cv]
       pdfplumber
       pytesseract
  2. In `docker-compose.yml` (or Dockerfile), install:
       - ghostscript
       - poppler-utils
  3. Rebuild container and confirm:
       python -c "import camelot, pdfplumber, pytesseract"
Goal:
  - No import errors in the container.
Integration:
  - CI config must mirror these changes.
```

---

### Prompt Section 3: Camelot Extraction Service

```
Context:
  - We need a standalone service for vector-PDF table extraction.
Task:
  1. Create `app/services/camelot_ocr.py`.
  2. Implement:
       def extract_tables_with_camelot(pdf_path: str, pages: str='all', flavor: str='lattice') -> List[pd.DataFrame]:
           tables = camelot.read_pdf(pdf_path, pages=pages, flavor=flavor)
           return [t.df for t in tables]
  3. Add support for `flavor='stream'` via parameter.
  4. Write `tests/test_camelot_ocr.py` using a known vector-PDF with tables—assert correct row/column counts.
Goal:
  - `pytest tests/test_camelot_ocr.py` passes.
Integration:
  - Make module ready for import by `run_ocr()`.
```

---

### Prompt Section 4: Tesseract Fallback Enhancement

```
Context:
  - For scanned PDFs, we need an image-based pipeline.
Task:
  1. Create/extend `app/services/tesseract_ocr.py`.
  2. For each page:
       a. Convert to PNG (use pdfplumber or pdf2image).
       b. Attempt `camelot.read_pdf(page_png, flavor='lattice', edge_tol=200)`.
       c. If `tables` empty, detect table regions (e.g. via pdfplumber page.find_tables) and OCR each crop with `pytesseract.image_to_string`.
       d. Return same structure as Camelot (List of DataFrames or List of cell-lists).
  3. Write `tests/test_tesseract_ocr.py` on a scanned-PDF sample—assert at least one table and correct parsing of a known cell.
Goal:
  - Scanned PDF → valid table output.
Integration:
  - Ready for `run_ocr()` fallback.
```

---

### Prompt Section 5: Unified OCR Pipeline

```
Context:
  - We now have `pdf_utils`, `camelot_ocr`, and `tesseract_ocr`.
Task:
  1. Refactor `app/services/ocr.py`’s `run_ocr(pdf_path)`:
       for each page_no:
         if is_text_page → tables = extract_tables_with_camelot(...)
         else            → tables = extract_with_tesseract(...)
         full_text = extract_full_text_via_pytesseract_or_pdfplumber
         collect {"page": page_no, "tables": tables_as_list_of_lists, "full_text": full_text}
       return List[...] 
  2. Preserve existing API signature for downstream code.
  3. Write `tests/test_ocr_integration.py` that feeds a mixed PDF and asserts the combined output shape.
Goal:
  - One pipeline entrypoint drives both paths seamlessly.
Integration:
  - Downstream parser can now assume uniform input.
```

---

### Prompt Section 6: Transaction Parser

```
Context:
  - `run_ocr()` now emits uniform tables + full_text.
Task:
  1. In `app/services/parser.py`, update `parse_transactions(ocr_output: List[dict])`.
  2. For each table row:
       - Map columns to fields: date, payee, amount, balance.
       - Use a date-helper to parse into full `datetime`.
       - Use regex to strip currency symbols and parse `Decimal`.
       - Construct `TransactionData(date, payee, amount, type, balance)`.
  3. Write `tests/test_parser.py` using a known sample PDF output (can mock `ocr_output`) to assert correct field values.
Goal:
  - Transaction model matches expected for sample data.
Integration:
  - This is the final data structure returned by the service.
```

---

### Prompt Section 7: Confidence Metrics & Logging

```
Context:
  - Sometimes Camelot mis-detects tiny or malformed tables.
Task:
  1. In `extract_tables_with_camelot`, compute `row_count` and `col_widths`.
  2. If `row_count < MIN_ROWS` or `wide_column_ratio > THRESHOLD`, log a warning and call Tesseract fallback instead.
  3. Ensure logs include both the attempted Camelot output and fallback output.
  4. Write `tests/test_camelot_confidence.py` simulating a tiny table (e.g. 1-row) and assert fallback path taken.
Goal:
  - Automatic detection of low-confidence tables.
Integration:
  - Keeps pipeline robust.
```

---

### Prompt Section 8: CI & Documentation

```
Context:
  - New code and system deps require updates to docs and CI.
Task:
  1. Update `README.md` with installation steps for Ghostscript/Poppler and new Python deps.
  2. Modify CI config (e.g. `.github/workflows/ci.yml`) to install system packages.
  3. Add new test files to the CI test suite.
Goal:
  - Fresh clone + CI build passes end-to-end.
Integration:
  - Project docs and pipeline in sync.
```

---


Prompt Section 9: HTTP Endpoint & Live curl Test
```
Context:
  - We have a working OCR + parser stack that returns a List[TransactionData].
  - We now need a simple HTTP API to verify end-to-end on real PDFs.
Task:
  1. In your web framework (FastAPI, Flask, etc.), add a new route:
       POST /extract-transactions
     that:
       • Accepts multipart/form-data file upload under key "file".
       • Saves to a temp path.
       • Calls our `run_ocr()` + `parse_transactions()` to get List[TransactionData].
       • Returns JSON serialized list.
  2. In `tests/`, create `test_integration_curl.sh`:
       ```bash
       #!/usr/bin/env bash
       for pdf in tests/sample_data/bank-statement-1.pdf \
                  tests/sample_data/bank-statement-2.pdf; do
         echo "Testing $pdf..."
         curl -s -F "file=@$pdf" http://localhost:8000/extract-transactions \
           | jq '.[0] | {date,amount,payee}' \
           > out.json
         # simple assertion: ensure date & amount fields exist
         test "$(jq -r '.date' out.json)" != null
         test "$(jq -r '.amount' out.json)" != null
       done
       echo "All curl tests passed."
       ```
  3. Make it executable and ensure CI runs it after the server is up.
Goal:
  - A single `bash tests/test_integration_curl.sh` yields “All curl tests passed.”
Integration:
  - Validates that the full pipeline works on real sample PDFs.

```