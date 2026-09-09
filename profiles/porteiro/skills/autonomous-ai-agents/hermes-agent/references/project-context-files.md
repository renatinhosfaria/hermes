# Project Context Files

Reference for the installed Hermes loader (`agent/prompt_builder.py`). Check
https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
when upgrading; discovery behavior has changed across releases.

## Startup discovery

One project-context type wins:

| Priority | Source | Discovery |
|---|---|---|
| 1 | `.hermes.md` / `HERMES.md` | Nearest match from working directory up to the Git root; not a merged chain. |
| 2 | `AGENTS.override.md` / `AGENTS.md` / `agents.md` | Merge the Git-root-to-CWD directory chain; first filename wins per directory, identical content deduplicated. |
| 3 | `CLAUDE.md` / `claude.md` | CWD. |
| 4 | `.cursorrules` and `.cursor/rules/*.mdc` | CWD. |

Outside a Git repository, AGENTS discovery checks only the working directory.
Subdirectory context can be discovered progressively during tool use; do not
claim that all parent and subdirectory AGENTS files are ignored.

SOUL.md is independent: the identity file is loaded from HERMES_HOME, not from
the working directory. For a named profile, HERMES_HOME is its profile directory.
A `.hermes.md` inside that directory is project context only when discovery
reaches it; it is not automatically loaded just because it is beside SOUL.md.

## Placement

Keep identity, posture and standing limits in SOUL.md, environment conventions
and skill routing in project context, and reusable procedures in skills loaded
with skill_view. A critical skill should have an explicit trigger in the
always-loaded identity when needed across working directories.

## Size and scanning

`context_file_max_chars`, when explicitly configured, controls the character
cap. Otherwise the loader scales it with model context (20,000–500,000 chars).
Oversized content is head/tail truncated. `context_file_read_timeout` defaults
to five seconds. Inspect actual loader output for truncation or `[BLOCKED: ...]`.
A threat scan can block a file's content; do not assume it merely removes the
matching sentence while preserving all other instructions.

`--ignore-rules` is a broad diagnostic isolation mode, not a selective way to
skip just one project file; check `hermes --help` for the installed behavior.
