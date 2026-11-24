# Plan: migrate `built-in-nyc-api` and `find-google-serp-url` into `networking-agent`

TODO item: *(migrate modules into `src`) Move the `built-in-nyc` and `google-serp-url`
modules into the networking-agent `src` folder to consolidate code under the
`networking-agent` repo.*

## Current state

- Both modules live **outside** `networking-agent/`, at the workspace root, and each is its own
  nested git repo (the parent repo only tracks them as gitlinks, with no `.gitmodules`).
- `built-in-nyc-api/src/` is a flat module folder (`api.py`, `models.py`). The backend reaches it
  with a `sys.path` insert driven by `config.BUILTIN_NYC_SRC`, then does `import api` /
  `from models import ...`. Those generic top-level names could collide with other modules.
- `find-google-serp-url` is an installable package (`google_serp`), installed into the backend
  venv with `-e ../../find-google-serp-url`. Its working tree has **uncommitted changes**
  (`cli.py`, `models.py`, `session.py`, `tests/test_cli.py`, `README.md`) that the backend
  already runs against.
- Baseline: backend 24 tests, google_serp 18, built-in-nyc 6, all passing. Ruff is clean on the
  backend.

## Target layout

Runtime code goes in `backend/src/` as real packages. Research scripts, captures and write-ups
are not runtime code, so they go under `networking-agent/research/` and `networking-agent/docs/`.

```
networking-agent/
├─ backend/
│  ├─ src/
│  │  ├─ builtin_nyc/          # was built-in-nyc-api/src/{api,models}.py
│  │  │  ├─ __init__.py        # re-exports get_jobs, get_companies and the models
│  │  │  ├─ api.py             # `from .models import ...` (relative import)
│  │  │  ├─ models.py
│  │  │  └─ AGENTS.md          # module notes (from built-in-nyc-api/AGENTS.md)
│  │  ├─ google_serp/          # was find-google-serp-url/src/google_serp/ (incl. uncommitted edits)
│  │  │  ├─ ...                # unchanged package; run as `python -m google_serp`
│  │  │  └─ AGENTS.md          # module notes (from find-google-serp-url/AGENTS.md)
│  │  └─ tools.py, config.py, ...
│  └─ tests/
│     ├─ builtin_nyc/test_api.py + fixtures/
│     └─ google_serp/test_cli.py, test_parser.py + fixtures/
├─ research/
│  ├─ builtin_nyc/inspect_page.py      # writes to research/builtin_nyc/out/ (gitignored)
│  └─ google_serp/*.py                 # write to research/google_serp/captures/ (gitignored)
└─ docs/
   ├─ builtin_nyc/prd.md
   └─ google_serp/README.md, results.md
```

Why the package name `builtin_nyc`: Python packages can't contain hyphens, and a named package
removes the `api`/`models` top-level names.

## Steps

1. **Clean base.** The backend is already committed (`85b2f1e`). Other uncommitted work
   (frontend, README, docs) is left alone, and the migration commit only includes the paths it
   touches.
2. **Keep history.** Fetch each nested repo's `HEAD` into the parent repo as tags
   `archive/built-in-nyc-api` and `archive/find-google-serp-url`. The old history stays
   reachable after the nested `.git` folders go away.
3. **Move files** into the target layout, using the *working-tree* copies so the uncommitted
   `google_serp` edits come along. Ignored local artifacts (`captures/`, `out/`, `.env`) move too,
   into gitignored locations, so nothing is lost.
4. **Code changes**
   - `builtin_nyc/api.py`: `from models import` → `from .models import`; add `__init__.py`.
   - `inspect_page.py` / research scripts: write output next to themselves (`Path(__file__)`).
   - `tools.py`: drop the `sys.path` hack; `from builtin_nyc import api as builtin_api`,
     `from builtin_nyc.models import ...`.
   - `config.py`: remove `BUILTIN_NYC_SRC` (and the now-unused `WORKSPACE_DIR`).
   - Tests: update imports (`from builtin_nyc import api`, `from builtin_nyc.models import ...`).
   - Ruff: the backend config (py311, `UP`/`B`/`I`) is stricter than the old repos', so run
     `ruff check --fix` / `ruff format` on the moved code and fix what remains.
5. **Dependencies.** In `backend/requirements.txt`, replace `-e ../../find-google-serp-url` with
   `playwright>=1.40`, and keep `requests` and `beautifulsoup4`. Uninstall the old editable
   `google-serp` from the backend venv so it can't shadow `src/google_serp`.
6. **Docs.** Update `networking-agent/README.md` and the moved module docs (`docs/v1/` is left as a
   historical record) and `.gitignore` (`research/**/captures/`, `research/**/out/`). Tick the TODO item.
7. **Remove the old folders.** Untrack the gitlinks (`git rm --cached`), then delete the old
   workspace-root folders. Their remaining contents are only `.git` (now archived as tags),
   `.venv` and caches.
8. **Verify.** All 48 tests pass from `backend/` (`pytest`), ruff is clean, and `server` and
   `tools` import. Then commit (Conventional Commits).

## Out of scope

- No behavior changes to either module.
- The `google-serp` console script (`google-serp.exe`) goes away; use `python -m google_serp`
  from `backend/src` instead.
