# Remember the user's resume and search parameters

Task: returning to the search page should not require re-uploading the resume or retyping
the search. Save the (compressed) PDF and the search parameters per user.

## Decisions

- **Resume storage** (`backend/src/userdata/saved_resume.py`):
  `database/users/<id>/resume/resume.pdf.gz` + `resume.json` (`filename`, `size`,
  `stored_size`, `uploaded_at`, cached parsed `profile`). Only the latest resume is kept;
  saving replaces both files atomically (tmp + replace). A corrupt metadata file reads as
  "nothing saved".
- **Compression: gzip level 9 of the raw bytes** (stdlib, no new dependency, lossless, so the
  download is byte-identical to the upload). pikepdf is not installed and pypdf stream
  recompression rewrites the file (not byte-identical) and was no better in a test (synthetic
  34,360-byte PDF with uncompressed streams: gzip 2,674 B = 7.8%; pypdf flate 2,851 B = 8.3%).
  Real resume PDFs already contain Flate streams, so expect a modest saving there; the point
  is lossless and dependency-free.
- **Parse once.** `POST /api/resume` parses (LLM) as before, then saves PDF + profile. A
  resume that fails to parse (415/413/422) is not saved. A storage failure is logged and does
  not fail the parse. `GET /api/resume/saved` serves the cached profile, so no re-parse.
- **Endpoints**: `GET /api/resume/saved` (metadata + profile, or `null`),
  `GET /api/resume/saved/file` (original PDF, 404 if none), `DELETE /api/resume/saved` (204,
  idempotent), `GET /api/search/params` (or `null`), `PUT /api/search/params`.
  CORS now allows DELETE.
- **Search parameters** (`userdata/search_params.py`): `database/users/<id>/search_params.json`,
  shaped like `SearchRequest` (`background`, `location`, `looking_for`, `boards`). It is a
  separate `SearchParams` model whose text fields may be empty (a draft), with the same
  `boards` normalization. The named-configurations task can reuse this shape. Saved on every
  `POST /api/search` (failure is logged, never blocks the search). Saving on edit
  is available via `PUT` but not wired in the UI (deferred).
- **Frontend.** `App` loads saved params and resume (with retry) on mount. The form is
  restored by remounting `Hero` (`key`), unless the user already searched or reopened a past
  search (`touched`), so history reopen is unaffected. `Hero` shows `SavedResumeChip`
  (name, size, saved date, Replace, Remove) instead of the upload box; Replace shows the
  upload box with "Keep saved resume". Saved params win over a stored resume's profile (the
  profile only fills the form on a fresh upload).
- **Git.** `database/users/*/resume/` added to `.gitignore` (personal data). `search_params.json`
  is not ignored (like `pins.json`); it is user input, not a document.

## Tests

`backend/tests/test_remember.py`; `frontend/src/App.test.tsx`,
`frontend/src/components/saved-resume.test.tsx`.
