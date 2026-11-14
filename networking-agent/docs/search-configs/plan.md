# Saved search configurations

Task: users can save named search configurations, see them in a right-hand panel on the search page, and load them back into the form.

## Storage

`database/users/<id>/search_configs.json` (module `backend/src/userdata/search_configs.py`):

    {"counter": 3, "configs": [{"id", "name", "params", "created_at", "updated_at"}]}

- `params` is the existing `SearchParams` (background, location, looking_for, normalized boards). Empty text is allowed; boards are normalized on save.
- `configs` is in creation order. A corrupt file reads as empty.
- `counter` is the highest default number ever handed out (see naming).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/search/configs` | creation order |
| POST | `/api/search/configs` | `{params, name?}` returns 201 |
| PATCH | `/api/search/configs/{id}` | `{name?, params?}` rename and/or overwrite |
| DELETE | `/api/search/configs/{id}` | 204 |

Names are trimmed; empty or over 80 characters returns 422. An explicit blank name on POST is rejected (it is not silently defaulted). Unknown ids return 404.

## Naming rule

Without a name, POST uses `Search Configuration #n`, where n = max(counter, highest `#k` among current default-named configs) + 1. The persisted counter means numbers are never reused, even when the highest one is deleted. A custom or renamed `Search Configuration #7` also counts, so the next default is #8.

## Frontend

- `components/search-configs.tsx`: the panel. `App.tsx` owns the data, and `Hero` reports its form through a new `onChange` prop (a ref, no re-render per keystroke). That value is the form as it would be searched, with boards filled in. The resume file is not included.
- Save: POST the current form, append the row, mark it loaded, and open it for renaming (the "name it on the side" flow).
- Rename: inline field with an accessible label. Enter saves, Escape cancels, and empty names are refused client-side. Server errors show in the panel.
- Load: sets the form and bumps `formVersion`, so the remount mechanism from the remember-params task applies (boards included). It also sets `touched`, so a late restore of the last params cannot clobber it. Loading marks the row `aria-current` and "Loaded".
- Overwrite: a per-row button PATCHes `params` with the current form.
- Delete: inline "Delete this one?" confirmation (Keep / Delete).
- Layout: shown only on the search view's form page. From `lg` it is a sticky 18rem column mirroring the history panel, with ScrollFade on the list. Below `lg` it wraps under the form (the root flex container wraps), and its list collapses behind a toggle button.

## Decisions and deferred

- Name uniqueness is not enforced.
- No undo for delete; confirmation is used instead.
- Loaded-row marking is not cleared when the form is edited afterwards (no "modified" indicator).
- History reopening and the last-params restore are unchanged.
