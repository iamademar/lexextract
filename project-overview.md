## Overview

A standalone, secure web application for a UK law firm to upload PDF bank statements (scanned or digital), extract structured transaction data into CSV, and ask natural-language questions via a chat interface.

**Timeline:** 2-week demo build (MVP) – not production
**Deliverables:**

* Code repository with developer README
* Brief user guide/walkthrough
* Test reports and sample CSVs
* Proprietary license (no open-source license)

---

## 1. Personas & Use Cases

**Paralegals:**

* Flag unusual transactions
* Reconcile dates between statements and ledgers
* Categorize payments

**Partners:**

* Obtain high-level spend summaries
* Approve client charges
* Audit compliance patterns

**Financial Clerks:**

* Generate reconciliations vs. internal ledgers
* Prepare CSV exports for accounting software
* Validate transaction metadata against source PDFs

---

## 2. Functional Requirements

### 2.1 Upload & Extraction

* **Endpoint:** `POST /upload/statement` accepts PDF
* **Process:** synchronous OCR → NLP parsing → CSV generation (≤5 min)
* **UI:** step-by-step status messages ("OCR running", "Parsing transactions", "Generating CSV")
* **Error feedback:** detailed (e.g., "OCR failed on page 3"), with retry

### 2.2 Chat Interface

* **Library:** Vercel AI Chatbot React components (default style)
* **LLM:** Mistral 7B (primary), LLaMA 2-7B backup
* **Deployment:** on same VM, CPU-only inference
* **Endpoint:** `POST /chat/message` (inputs: statement\_id, message)

### 2.3 History & Feedback

* **Storage:** transcripts in PostgreSQL; manual deletion only
* **UI:** History page listing sessions by date, statement name; filters by date, name, keywords; View & Delete buttons
* **Feedback:** thumbs up/down; down-logs silently for later review

### 2.4 Downloads & Deletion

* **CSV download:** `GET /download/csv/{statement_id}`
* **Manual deletion:** admin dashboard (`DELETE /uploads/{statement_id}`), accessible to IT manager

---

## 3. Non-Functional & Security

* **Compliance:** GDPR & UK Data Protection Act
* **Auth:** standalone username/password; OAuth2 password flow with JWTs (access 1 h, refresh 7 d)
* **Password policy:** min 8 chars, 1 uppercase, 1 number, 1 symbol; self-service reset (1 h token)
* **Storage:**

  * **VM:** Ubuntu 22.04 LTS, 4 vCPU, 16 GB RAM, 100 GB SSD
  * **FS layout:** `/var/app/data/uploads/{userId}/{YYYYMMDD_HHMMSS}_{orig}.pdf`; `/var/app/data/exports/{userId}/{YYYYMMDD_HHMMSS}_{orig}.csv`
  * **Env:** `.env` in `/var/app/`, owner `app:app`, mode `600`
* **Logging:** user actions and OCR/LLM errors in PostgreSQL; retained until manual purge

---

## 4. Architecture & Tech Stack

| Layer                 | Technology                                |
| --------------------- | ----------------------------------------- |
| OS                    | Ubuntu 22.04 LTS                          |
| Web server & API      | FastAPI (Python, latest); Uvicorn         |
| Frontend              | React + Vercel AI Chatbot                 |
| OCR                   | PaddleOCR                                 |
| LLM                   | Mistral 7B (primary), LLaMA 2-7B (backup) |
| Database              | PostgreSQL                                |
| Auth                  | OAuth2 password flow, JWT bearer tokens   |
| Deployment            | Single VM (manual bash scripts)           |
| Dependency management | `venv` + `requirements.txt`               |
| CI/CD                 | pytest tests (≥80% coverage), trunk-based |

---

## 5. API Endpoints

```text
POST   /auth/login                → JWT access & refresh tokens
POST   /auth/refresh              → New access token
POST   /auth/forgot-password      → Send reset link (console)
POST   /auth/reset-password       → Reset via token

POST   /upload/statement         → Accept PDF, return statement_id
POST   /process/statement        → OCR+parse sync, return CSV URL & summary
GET    /download/csv/{id}        → Download CSV

POST   /chat/message             → Send user query, return AI reply

GET    /history/sessions         → List chat sessions (filters)
GET    /history/session/{id}     → Get transcript
DELETE /history/session/{id}     → Delete session

DELETE /uploads/{id}            → Delete PDF, CSV, history
```

---

## 6. Demo Scope & Samples

* **Sample PDFs:** 3–5 publicly available statement formats
* **Sample queries:**

  1. "What’s the total paid in June 2025?"
  2. "List all transactions on 15/05/2025 over £500"
  3. "Show me a CSV of all debit entries"
* **CSV fields:** Date (YYYY-MM-DD), Payee, Amount (decimal), Type (Debit/Credit), Running Balance, Currency (ISO code)
* **Acceptance:** ≥95% extraction accuracy; chat responses <5 s; no critical UI bugs

---

## 7. Deliverables

* Git repo (proprietary) with README
* Brief user guide/walkthrough
* Test reports + sample CSVs
* Manual deployment instructions (bash scripts)

