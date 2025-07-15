**High-Level Blueprint**

1. **Integrate “Clients” into the Sidebar**

   * Modify the existing sidebar component to add a “Clients” link pointing to `/clients`.
   * Verify navigation by creating a placeholder page at `/clients`.
2. **Define API Utilities**

   * Under `lib/api/clients.ts`, implement:

     * `fetchClients()` → `GET /clients/`
     * `fetchClient(id)` → `GET /clients/{id}`
     * `createClient(data)` → `POST /clients/`
     * `updateClient(id, data)` → `PUT /clients/{id}`
     * `deleteClient(id)` → `DELETE /clients/{id}`
   * Write tests to mock these endpoints.
3. **Build Clients List UI**

   * Create a `ClientsList` component that:

     * Calls `fetchClients()`.
     * Renders a table or list of clients (name, contact name, email).
     * Shows loading and error states.
4. **Build ClientForm Component**

   * Reusable form for **Create** and **Edit** modes.
   * Fields: `name`, `contact_name`, `contact_email`.
   * Validation on required fields.
5. **Wire Create Workflow**

   * On `/clients`, add an “Add Client” button.
   * Clicking opens `ClientForm` in **create** mode.
   * On submit, call `createClient()`, close form, refresh list.
6. **Wire Edit Workflow**

   * Each row in `ClientsList` has an “Edit” button.
   * Clicking opens `ClientForm` pre-filled with the client’s data.
   * On submit, call `updateClient()`, close form, refresh list.
7. **Wire Delete Workflow**

   * Each row has a “Delete” button.
   * Clicking prompts for confirmation.
   * On confirm, call `deleteClient()`, refresh list.
8. **Comprehensive Testing & Polishing**

   * For each feature: write tests first (component, hook, utils).
   * Mock API with MSW.
   * Cover success, loading, and error paths.
   * Ensure styling consistency with existing UI.

---

## Iterative Chunks

1. **Sidebar & Routing**
2. **API Utilities**
3. **ClientsList Component**
4. **ClientForm Component**
5. **Create Client Flow**
6. **Edit Client Flow**
7. **Delete Client Flow**
8. **Error/Loading States & Final Tests**

---

## Chunk 3 (“ClientsList Component”) → Smaller Steps

1. **3.1** Write a test for `fetchClients()` in `lib/api/clients.ts` that mocks `GET /clients/`.
2. **3.2** Implement `fetchClients()` using `fetch()` or `axios`.
3. **3.3** Write a test for `ClientsList` that mocks `fetchClients()` and verifies rendering of client rows.
4. **3.4** Implement `ClientsList.tsx`: call `fetchClients()`, show loading, error, then table.
5. **3.5** Add basic styling/skeleton state matching existing UI.

*(Repeat this breakdown for each chunk to ensure steps are small, test-driven, and integrate fully before moving on.)*

---

## Prompts for a Code-Generation LLM

```text
# Prompt 1: Sidebar Navigation Link for Clients (TDD)
Write a Jest test using React Testing Library for the `AppSidebar` component (in `frontend/lexextract-chat/components/app-sidebar.tsx`) that verifies:
- A link with text "Clients" is present
- That link’s `href` is "/clients"

Then implement:
1. Add the `<SidebarLink to="/clients">Clients</SidebarLink>` in `AppSidebar`.
2. Create a placeholder Next.js page at `frontend/lexextract-chat/app/clients/page.tsx` exporting `export default function ClientsPage() { return <h1>Clients</h1>; }`.
```

```text
# Prompt 2: API Client Utilities (TDD)
In `frontend/lexextract-chat/lib/api/clients.ts`, first write Jest tests using MSW to mock:
- `GET /clients/`
- `GET /clients/:id`
- `POST /clients/`
- `PUT /clients/:id`
- `DELETE /clients/:id`

Verify that each utility function (`fetchClients`, `fetchClient`, `createClient`, `updateClient`, `deleteClient`) issues the correct HTTP method and URL.

Then implement those five functions using `fetch` or `axios`, returning parsed JSON or status as appropriate.
```

```text
# Prompt 3: ClientsList Component (TDD)
Write a unit test for a new component `ClientsList` (`frontend/lexextract-chat/components/ClientsList.tsx`) that:
- Mocks `fetchClients()` to return an array of clients
- Verifies that each client’s name, contact name, and email appear in the rendered list

Then implement `ClientsList`:
1. Call `fetchClients()` on mount (e.g. in a custom `useClients` hook)
2. Display a loading spinner while fetching
3. Display an error message on failure
4. Render a table or list with the client data
```

```text
# Prompt 4: ClientForm Component (TDD)
Create tests for `ClientForm` (`frontend/lexextract-chat/components/ClientForm.tsx`) that:
- Renders input fields for `name`, `contact_name`, `contact_email`
- Calls `createClient` when submitted in create mode
- Calls `updateClient` when submitted in edit mode with pre-filled values

Then implement `ClientForm` using React Hook Form (or controlled inputs), client-side validation, and calls to the API utilities. Ensure form resets or closes on success.
```

```text
# Prompt 5: Add Create Client UI (TDD)
On the `/clients` page (`app/clients/page.tsx`), write a test that:
- Finds and clicks an “Add Client” button
- Verifies that `ClientForm` opens in a modal or drawer
- Mocks `createClient` and verifies that on successful submit, the new client appears in `ClientsList`

Then implement:
1. Add “Add Client” button to `ClientsPage`
2. Render `ClientForm` in create mode (e.g. via a modal component)
3. Refresh the `ClientsList` on success
```

```text
# Prompt 6: Edit Client UI (TDD)
Write a test for `ClientsList` that:
- Finds an “Edit” button on a client row
- Clicks it and verifies `ClientForm` opens with that client’s data pre-filled
- Mocks `updateClient` and verifies the list updates on submit

Then implement:
1. Add “Edit” buttons to each row
2. Wire up passing `client` prop into `ClientForm` in edit mode
3. Refresh the list on successful update
```

```text
# Prompt 7: Delete Client UI (TDD)
Write a test that:
- Finds a “Delete” button on a client row
- Clicks it and confirms a confirmation dialog appears
- Mocks `deleteClient` and verifies the client is removed from the list on confirm

Then implement:
1. Add “Delete” buttons to each row
2. Show a confirmation (`window.confirm` or custom dialog)
3. Call `deleteClient` and refresh the list on success
```

```text
# Prompt 8: Error and Loading States (TDD)
For each of the components (`ClientsList`, `ClientForm` workflows), write tests that simulate:
- Slow network → verify loading spinners appear
- API errors → verify error messages are displayed and retry options exist

Then implement:
- Spinners or skeleton screens during fetches/submits
- User-friendly error messages and retry buttons or form error displays
```

---

This structure gives you:

* A clear, end-to-end blueprint
* Iterative chunks with small steps
* Test-first prompts for a code-generation LLM that build on each other and integrate fully.
