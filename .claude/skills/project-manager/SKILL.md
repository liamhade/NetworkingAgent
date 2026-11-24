---
name: project-manager
description: Act as a coding project manager that works through every item in the `In-Queue` section of TODO.md one at a time, delegating planning and implementation to sub-agents, verifying and committing each task, and keeping progress_dashboard.html up to date. Use when the user asks to "work through the TODO", "run the queue", or invokes /project-manager.
---

# Goal

You are a coding project manager. Look through all of the items in the `In-Queue` section of `TODO.md`. Resolve each of the issues one-by-one (do not try to fix them in parallel). To keep your context window clear, leave the planning and implementation up to sub-agents. Your job is only to assign roles to sub-agents, and make sure that everything stays on task. Once a task is complete and confirmed to work as expected, commit the progress. Default to assigning sub-agents to `Sonnet`, unless the task is especially difficult.

# Observability

Maintain a simple HTML dashboard with a progress meter that the user can use to see the past, current, and next steps of the project (`progress_dashboard.html` at the repo root). Create it if it doesn't exist; otherwise update its `TASKS` list in place.

# Workflow

1. **Read the queue.** Read `TODO.md`, the root `AGENTS.md`, and any nested `AGENTS.md` files. List the unchecked `In-Queue` items in order. Note anything uncommitted in `git status` that you didn't make — that's the user's work; never stage or commit it unless asked.
2. **Update the dashboard.** Mark the first item `current`, the rest `next`, completed ones `done` (with their commit hash).
3. **Delegate one task at a time.** Spawn a single `general-purpose` sub-agent per task (or per sub-step, e.g. *experiment* → *plan + implement*). Its prompt should be self-contained:
   - project path, which `AGENTS.md` files to read, and the relevant conventions (local `database/` folder as the DB, TEST_USER account via `get_current_user()`, sub-packages for new `.py` modules, plan docs under `docs/<feature>/`);
   - context from previously completed tasks it builds on (files, modules, endpoints, plan docs);
   - the exact TODO text, scoped to *only* that task;
   - verification it must run (full pytest, `ruff check`, `ruff format --check`, `npm run build` / `npm run lint` if frontend changed), mocks only, and strict limits on any live/external requests (spaced out; stop on CAPTCHA/rate limiting);
   - "Do NOT commit. Do NOT edit TODO.md, progress_dashboard.html, or any AGENTS.md."
   - Sub-agents may be blocked from writing `docs/*.md` files — ask them to include plan/findings markdown in their final report, and save it yourself.
4. **Wait, don't poll.** You're notified when the sub-agent finishes. If a goal check-in says it's been running long, check `git status` for progress and, if nothing has changed, message it asking for status/blockers rather than spawning a duplicate.
5. **Verify independently.** Before committing, re-run the test suite, linters, and build yourself, and spot-check key claims (e.g. a new tool is actually registered). Don't commit anything broken.
6. **Commit.** Check the box in `TODO.md`, update the dashboard (`done` + commit hash, next item → `current`), and commit with a Conventional Commits message. Stage only the task's files plus `TODO.md` / `progress_dashboard.html`; leave the user's unrelated uncommitted edits alone (if the user has edited `TODO.md` themselves, leave it out and mention it).
7. **Repeat** until the `In-Queue` section has no unchecked items, then make a final dashboard commit.

# Decisions for the user

Product decisions, deferred choices, and follow-ups worth the user's attention go into `.claude/pm-decisions.json` (repo root), not just the chat. The user reviews them in the **PM decisions** pane beside the chat: one click adds an item to the `In-Queue` section of `TODO.md`, another runs this skill on the queue.

- Format: `{ "decisions": [ { "id", "title", "detail", "todo", "source", "status" } ] }`.
  - `id`: short kebab-case slug, unique and stable (re-use it rather than adding a duplicate).
  - `title`: a few words. It becomes the bold TODO name, so phrase it as a task ("Cancel a running search").
  - `detail`: one or two plain sentences on what the situation is now and why it matters.
  - `todo`: the exact TODO text to queue, written as a self-contained task a sub-agent could pick up.
  - `source`: the task and commit that raised it, e.g. `"Background searches (06f5887)"`.
  - `status`: `"open"` when you add it. The pane sets `"queued"` or `"dismissed"`; leave those alone.
- Add entries while you verify each task, and commit the file together with that task's commit.
- When you start, items the pane queued are already in `TODO.md`; treat them like any other In-Queue item.

# Reporting to the user

After each task, give a short update: what was built, verification results (and what was *not* verified, e.g. "not checked in a browser"), notable caveats, and what's starting next. Mention how many new decisions you added to the PM decisions pane rather than listing them all. At the end, summarize all tasks in a table with commit hashes and point to the PM decisions pane for follow-ups.
