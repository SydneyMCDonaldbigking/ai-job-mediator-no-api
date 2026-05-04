# Chat History And Master Resume Design

## Goal

Unify chat history persistence with the existing backend TinyDB store, add a reliable delete-thread flow, and make repeated resume uploads overwrite the current master resume instead of creating a new master record.

## Scope

This design covers:

- master resume overwrite behavior on repeated upload
- backend TinyDB storage for chat users, threads, steps, feedback, and elements metadata
- frontend migration from local JSON thread storage to backend-backed thread storage
- explicit frontend actions for re-uploading the master resume and deleting the current thread
- JD-tailored ATS PDF download from the Chainlit frontend

This design does not include:

- per-message deletion
- migration to SQLite or another database engine
- server-side storage of binary chat assets in TinyDB

## Existing State

- resumes, jobs, and improvements already live in backend TinyDB
- chat history is currently stored in frontend-local JSON files under `frontend/data/chats`
- chat attachments are currently persisted as files under `frontend/public/chat-assets`
- the frontend is a single Chainlit `app.py` with a custom data layer

## Proposed Architecture

### 1. Master Resume Upload Overwrite

- Keep a single active master resume record in TinyDB.
- When the user uploads a new master resume, update the existing master record in place.
- Preserve the same `resume_id` so active thread metadata and frontend session state do not break.
- Reset stale derived fields on overwrite:
  - `processed_data`
  - `cover_letter`
  - `outreach_message`
  - `title`
  - `original_markdown`
  - `processing_status`

### 2. Backend Chat History Store

- Add `chat_users` and `chat_threads` TinyDB tables.
- Store each thread as one nested record with:
  - thread metadata
  - steps
  - elements metadata
- Keep feedback nested on steps, matching current frontend structure.
- Reuse the current local JSON record shape as much as possible to minimize frontend changes.

### 3. Chat History API

Expose a private frontend-facing API under `/api/v1/chat` for:

- users: get/create
- threads: get/list/upsert/delete
- steps: upsert/delete
- elements: get/upsert/delete
- feedback: upsert/delete
- thread author lookup
- favorite steps lookup

The API should be shaped so the frontend data layer can preserve the existing Chainlit `BaseDataLayer` method signatures.

### 4. Frontend Data Layer Migration

- Introduce a backend-backed data layer that talks to `/api/v1/chat`.
- Keep local asset file persistence in `frontend/public/chat-assets` for now.
- Use backend TinyDB only for thread/user/message metadata and restore state from there.
- Keep the old local JSON store as a legacy reader for one-time migration and test compatibility.

### 5. Legacy Thread Migration

- On first thread-list access for a user, if backend thread storage is empty but local JSON thread files exist, import those local threads into backend TinyDB.
- Preserve thread ids and metadata.
- Rebind imported threads to the current persisted backend user id so list/filter behavior keeps working.

### 6. Frontend Actions

Add explicit Chainlit actions:

- `重新上传主简历`
- `删除当前对话`
- `下载 ATS PDF`

Behavior:

- re-upload opens the same file upload entry used at start
- delete removes the current thread from backend storage and tells the user the conversation has been cleared
- PDF download uses the current master resume plus the current JD and attaches the generated PDF back into the chat

## ATS PDF Flow

- Store the last JD used for optimization/evaluation in thread/session metadata.
- Add a frontend backend-client method for `POST /api/generate-tailored-pdf`.
- Generate the PDF from the current master resume content and the remembered JD.
- Return a `cl.File` attachment so the user can download it directly from chat.

## Error Handling

- If the user asks for a PDF before a JD is known, ask them to paste the target JD first.
- If the current thread has been deleted, the next user message should recreate a fresh thread cleanly.
- Migration should be best-effort: log failures and continue with empty backend history instead of crashing the app.

## Testing Strategy

### Backend

- integration tests for chat history endpoints
- integration test proving repeated upload overwrites the current master resume record

### Frontend

- client tests for ATS PDF generation
- backend-backed data layer tests for list/get/delete thread operations
- smoke test for helper wiring around action construction and PDF attachment generation
