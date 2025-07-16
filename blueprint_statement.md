Below is a three-layer breakdown: first a high-level blueprint, then an intermediate set of iterative chunks, then a fully expanded list of small, safely testable steps. Finally you’ll find a series of TDD-style prompts (each in a separate code block tagged as `text`) that build on each other—ensuring every piece is wired together with tests.

---

## High-Level Blueprint

1. **Project Scaffolding**
   Set up backend and frontend directories, dependencies, environment.

2. **Database Schema**
   Extend `statements` table to track progress & status.

3. **Backend API**

   * **Upload** endpoint to accept statement PDFs.
   * **Processing** service to parse and persist transactions.
   * **Progress** endpoint to poll creation progress.
   * **Transactions** endpoint to fetch created transactions.

4. **Frontend UI**

   * **Sidebar**: add “Statements” link.
   * **List Page**: upload form + list of statements.
   * **Show Page**: progress bar + transactions table.

5. **Real-time Updates**
   Polling (or WebSocket) to drive live progress indicator.

6. **Testing**
   Unit & integration tests each step, TDD-style.

---

## Iterative Chunks

1. **Schema Migration + Model Update**
2. **Statement Upload Endpoint**
3. **Background Processing Service**
4. **Progress Tracking API**
5. **Sidebar Link Integration**
6. **Statements List & Upload UI**
7. **Statement Show & Progress UI**
8. **Transactions Display UI**
9. **End-to-End Testing & Documentation**

---

## Detailed Small-Step Plan

### 1. Schema Migration + Model Update

* Write Alembic migration:

  * Add `progress` (Integer, default 0).
  * Add `status` (Enum or String with CHECK, default `'pending'`).
* Update `Statement` model with new fields & defaults.
* Add tests verifying new columns exist with correct defaults.

### 2. Statement Upload Endpoint

* Create `backend/app/routers/statements.py`.
* Define POST `/statements?client_id={int}`:

  * Validate `client_id`.
  * Accept `UploadFile` (PDF only).
  * Save file under `uploads/statements/…`.
  * Create `Statement` record (`status='pending'`, `progress=0`).
  * Return 201 + JSON body.
* Write unit tests for success, missing/invalid `client_id`, invalid file.

### 3. Background Processing Service

* Create `backend/app/services/statements.py`.
* Implement `async def process_statement(statement_id: int)`:

  * Load statement, set `status='processing'`.
  * Call existing parser → list of transactions.
  * Insert each `Transaction`, increment `progress`.
  * On success set `status='completed'`, on error set `status='failed'`.
* Wire into POST endpoint via `BackgroundTasks`.
* Write tests mocking parser, verifying DB updates & error paths.

### 4. Progress Tracking API

* In statements router, add GET `/statements/{id}/progress`:

  * Return `{ progress, status }`.
* Tests for all statuses and 404 case.

### 5. Sidebar Link Integration

* Edit `frontend/lexextract-chat/components/nav-sidebar.tsx` (or `app-sidebar.tsx`):

  * Add `<NavLink href="/statements">Statements</NavLink>`.
* Write React test to assert navigation.

### 6. Statements List & Upload UI

* Create `frontend/lexextract-chat/app/statements/page.tsx`:

  * Fetch GET `/api/statements`.
  * Render list (ID, client, date).
  * File input + client dropdown → POST `/api/statements?client_id=…`.
  * On success redirect to `/statements/{id}`.
* Write component tests.

### 7. Statement Show & Progress UI

* Create `frontend/lexextract-chat/app/statements/[id]/page.tsx`:

  * On mount fetch statement details.
  * Poll `/api/statements/{id}/progress` every second.
  * Render a progress bar & status.
  * When `status==='completed'`, stop polling & fetch transactions.
* Component tests simulating poll states.

### 8. Transactions Display UI

* In show page, after completion fetch `/api/statements/{id}/transactions`.
* Render using `Table` component: Date, Payee, Amount, Type, Balance, Currency.
* Write integration tests for table rendering.

### 9. End-to-End Testing & Documentation

* Write E2E test (Playwright/Cypress) covering upload → progress → table.
* Update README: new endpoints, frontend routes, usage.

---

## TDD-Style Prompts for a Code-Gen LLM

### Prompt 1: Migration & Model Update

```text
Context:
In the LexExtract FastAPI backend, we need to track the progress of transaction creation for statements. The existing `statements` table lacks progress or status fields.

Task:
Write an Alembic migration that:
- Adds `progress` (Integer, non-null, default=0) to the `statements` table.
- Adds `status` (String, non-null, default='pending') with allowed values ['pending','processing','completed','failed'] (use an `Enum` or `CHECK` constraint).

Then update `backend/app/models.py`:
- Extend the `Statement` ORM model to include `progress` and `status` with appropriate SQLAlchemy defaults.

Finally, add a test in `backend/tests/test_db.py` verifying the new columns exist and have the correct defaults.
```

### Prompt 2: Upload Endpoint

```text
Context:
We want to allow clients to upload PDF statements, which will later be processed into transactions.

Task:
Create `backend/app/routers/statements.py` and register it in `main.py`. In it, implement:
POST `/statements?client_id={int}`:
- Validate `client_id` exists (404 if not).
- Accept `file: UploadFile` and ensure it’s a PDF.
- Save the upload to `uploads/statements/{new_statement_id}.pdf`.
- Create a `Statement` record with `status='pending'` and `progress=0`.
- Return HTTP 201 with the created statement’s JSON.

Write unit tests in `backend/tests/test_statements.py` covering:
- Successful upload.
- Missing `client_id` (422 error).
- Nonexistent `client_id` (404).
- Non-PDF upload (400 or 422).
- Filesystem save errors (simulate via patch).
```

### Prompt 3: Background Processing Service

````text
Context:
After upload, statements must be processed asynchronously to extract transactions and update progress.

Task:
In `backend/app/services/statements.py`, implement:
```python
async def process_statement(statement_id: int):
    # 1. Load Statement, set status='processing'
    # 2. Use parser.run_extraction(...) to get List[dict]
    # 3. For each txn in the list:
    #      - Insert a Transaction record linked to statement_id
    #      - Increment statement.progress (e.g. by 100/total_count) and commit
    # 4. On success set status='completed', on exception set status='failed'
````

Modify the POST endpoint to enqueue this via FastAPI’s `BackgroundTasks(process_statement, statement.id)` immediately after saving the statement.

Write tests in `backend/tests/test_process_statement.py`:

* Mock parser output of N transactions.
* Assert N Transaction rows, correct progress increments.
* Simulate parser exception → status='failed'.

````

### Prompt 4: Progress Tracking API
```text
Context:
Clients need to poll for processing progress.

Task:
In `backend/app/routers/statements.py`, add:
GET `/statements/{statement_id}/progress`:
- 404 if not found.
- Return JSON `{ "progress": int, "status": str }`.

Write unit tests in `backend/tests/test_progress_endpoint.py` for:
- Each status value (pending, processing, completed, failed).
- 404 on invalid ID.
````

### Prompt 5: Sidebar Link Integration

````text
Context:
The Next.js frontend needs a new “Statements” link in its sidebar.

Task:
Edit `frontend/lexextract-chat/components/nav-sidebar.tsx` (or `app-sidebar.tsx`) to insert:
```jsx
<NavLink href="/statements">Statements</NavLink>
````

Write a Jest + React Testing Library test to confirm the link renders and navigates to “/statements” on click.

````

### Prompt 6: Statements List & Upload UI
```text
Context:
Users must see existing statements and upload new ones.

Task:
Create `frontend/lexextract-chat/app/statements/page.tsx`:
- On load, fetch GET `/api/statements`.
- Render a list: ID, client name, upload date, link to `/statements/{id}`.
- Include a file upload form (accept=".pdf") plus client selector or hidden client_id.
- On submit, POST to `/api/statements?client_id={clientId}`, then router.push to `/statements/{newId}`.
- Display validation/errors.

Add component tests (Jest+RTL) covering rendering list, upload success, and error states.
````

### Prompt 7: Statement Show & Progress UI

```text
Context:
After upload, the user should see live progress.

Task:
Create `frontend/lexextract-chat/app/statements/[id]/page.tsx`:
- Fetch statement details on mount.
- Begin polling `/api/statements/{id}/progress` every 1s.
- Render a `<progress>` bar and status text.
- When status==='completed', stop polling and fetch `/api/statements/{id}/transactions`.
- Maintain clean unmounting.

Write tests simulating:
- Initial pending → processing → completed transitions.
- Correct cleanup of polling.
```

### Prompt 8: Transactions Display UI

```text
Context:
Once processing is done, show the extracted transactions.

Task:
In the show page, after fetching `/api/statements/{id}/transactions`, render a table with columns:
Date | Payee | Amount | Type | Balance | Currency.
Ensure the UI gracefully handles zero, few, and many rows (optional pagination). Use existing `Table` component.

Write a test that mocks the transactions API and asserts the table renders correctly.
```

### Prompt 9: End-to-End Testing & Documentation

```text
Context:
All pieces are built; we need an end-to-end smoke test and docs.

Task:
1. Write an E2E test (Playwright/Cypress or Jest+Puppeteer) that:
   - Visits `/statements`.
   - Uploads a sample PDF.
   - Waits for the progress bar to reach 100%.
   - Verifies that the transactions table appears.

2. Update the project README:
   - Document new endpoints (`POST /statements`, `GET /statements/{id}/progress`, `GET /statements/{id}/transactions`).
   - Show snippets of how to call them.
   - Explain the frontend routes and behavior.

Deliver both the test file and the updated README section.
```
