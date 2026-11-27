# Overview

The purpose of this workspace is to collect different tools that will be useful for the `Networking Agent`. The `Networking Agent` is the name I have given to a project where you type in your job search parameters, and it will give you a list of companies to look at, people to connect with, and jobs to apply to.

# Using the TODO

After you complete a task from the `TODO.md` check of the box.

# Version-Control

Always benchmark your work by making committing meaningful, working changes (don't save something that's broken).

Use the `Conventional Commits` format for saving work.

# Folder Structure

The app lives at the repo root: `backend/` (FastAPI), `frontend/` (Vite + React), `research/` (scripts, not used at runtime), `docs/`, and the `Dockerfile`.

Use a `Service Oriented` folder structure to group files in the `backend`.

# Documentation

For any large change you are going to make, write up the plan for that change into `docs/` so that there is auditability of the development process.

# Code Intelligence (Python LSP)

Python code is served by Pyright through a local Claude Code plugin at `tools/claude-plugins/python-lsp/`. Use it for definitions, references and type errors in `backend/` instead of grepping for symbol names.

- Config: `pyrightconfig.json` at the repo root. It includes `backend/` and sets `extraPaths: ["backend/src"]`, because backend modules import each other as top-level names (for example `from schemas import ...`). Keep that setting when adding modules.
- Start Claude Code with the plugin loaded. Plugins are not picked up mid-session:
  `claude --plugin-dir "c:\Users\Liam Hade\Desktop\NetworkingAgent\tools\claude-plugins\python-lsp"`
- The server binary is referenced by its 8.3 short path in `tools/claude-plugins/python-lsp/.lsp.json`. Claude Code rejects command paths with spaces, so don't replace it with the long path. If Python or Pyright moves, update that file.
- Check that it loads with `/plugin` (Errors tab should show nothing for `pyright`) or `claude --debug`.
- The VS Code diagnostics tool only sees files that are open in the editor, so an empty result is not proof a file is clean. Run `python -m pyright --project pyrightconfig.json <path>` for a full check.

# Database

Eventually, I'm going to migrate the database to `Supabase`. For this POC, to keep the ball rolling, let's just use the local `database` folder as the database we're going to use. It holds personal data and is gitignored: never commit it.

I'm also going to add separate accounts in the future. But for now, we're going to test using the "TEST_USER" account.