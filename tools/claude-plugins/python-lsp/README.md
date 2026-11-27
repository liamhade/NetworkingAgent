# python-lsp (Claude Code plugin)

Registers the Pyright language server with Claude Code so it can use
compiler-accurate definitions, references and diagnostics for Python.

## Setup

1. Install Pyright for the Python that runs Claude Code:

   ```
   python -m pip install --user pyright
   ```

   This puts `pyright-langserver.exe` in `%APPDATA%\Python\Python314\Scripts`.
   If your Python version differs, update the `command` path in `.lsp.json`.
   The path uses the 8.3 short name (`LIAMHA~1`) because Claude Code rejects
   command paths with spaces unless they start with `/`.

2. Start Claude Code with this plugin loaded:

   ```
   claude --plugin-dir "c:\Users\Liam Hade\Desktop\NetworkingAgent\tools\claude-plugins\python-lsp"
   ```

## Verify

- Run `/plugin` and check the Errors tab. Expect no entries for `pyright`.
- Run `claude --debug`. A failed start logs `LSP server pyright failed to start`.

Import roots are set in the repo-level `pyrightconfig.json`
(`extraPaths: ["backend/src"]`), because the backend imports modules such as
`schemas` and `userdata` directly from `backend/src`.
