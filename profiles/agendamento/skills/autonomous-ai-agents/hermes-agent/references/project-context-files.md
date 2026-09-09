# Project Context Files

Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
Implementation: `agent/prompt_builder.py` in the installed Hermes source.

## Discovery

Only one project context type wins at startup, in this order:

| File | Discovery |
|---|---|
| `.hermes.md` / `HERMES.md` | Nearest matching file walking toward the git root; not a merged chain |
| `AGENTS.override.md` / `AGENTS.md` | Within a repository, merge the directory chain from git root to cwd; the override replaces AGENTS.md in its directory |
| `CLAUDE.md` | Working directory |
| `.cursorrules` / `.cursor/rules/*.mdc` | Working directory |

Outside a repository, the AGENTS.md startup check is limited to cwd. During a
session, supported subdirectory hints may be discovered progressively as tools
access paths; see `agent/subdirectory_hints.py` for the installed behavior.

SOUL.md is independent: it supplies identity from HERMES_HOME, not cwd.
Use it for identity, communication and durable limits. Keep environment paths
and conventions in project context; put procedures and contracts in skills.

Kanban workers pin their working directory to the task workspace. Selecting a
profile does not guarantee its home-level .hermes.md will be loaded. Keep the
required skill-loading instruction in SOUL and the full procedure in the skill.

## Limits and scanning

An explicit `context_file_max_chars` controls truncation. Otherwise the cap scales
with model context length, with a 20,000-character floor and 500,000 ceiling.
Oversized content is head/tail truncated. Read timeout is controlled by
`context_file_read_timeout` (default 5 seconds).

Context files are scanned before prompt inclusion. A detected threat replaces
the file content with a BLOCKED marker; the rest of that file is not retained.
Check the loaded result, not just whether the file exists.

`--ignore-rules` also skips SOUL and other user customization; it is a diagnostic
mode, not an ordinary way to run this profile's authorized workflow.
