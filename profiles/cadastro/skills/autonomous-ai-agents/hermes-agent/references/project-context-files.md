# Project Context Files

Validated against the installed Hermes prompt builder (2026-09-09).
Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files

## Discovery

Only the first matching project context type is selected:
`.hermes.md` / `HERMES.md`, then `AGENTS.override.md` / `AGENTS.md`,
then `CLAUDE.md`, then Cursor rules.

- `.hermes.md`: nearest matching file while walking toward the git root;
  not a merge of all ancestor `.hermes.md` files.
- `AGENTS.md`: within a git repository, merge the directory chain from git root
  through CWD. `AGENTS.override.md` replaces `AGENTS.md` in its directory.
  Outside a git repository, only CWD is checked at startup. Additional
  subdirectory context can be discovered progressively during tool use.
- `SOUL.md`: independently loaded from HERMES_HOME as identity, not from CWD.

## Placement

Keep identity and durable principles in SOUL.md. Keep local paths and repo
conventions in project context. Put procedures and tool contracts in skills.
A named profile does not guarantee that its `.hermes.md` is loaded: CLI launch
location and the task workspace matter. Kanban workers pin TERMINAL_CWD to the
workspace, which may be outside the profile directory.

## Limits and scanning

An explicit positive `context_file_max_chars` overrides the cap. Otherwise,
the cap scales with model context (floor 20,000; ceiling 500,000 characters).
Oversized files are head/tail truncated with a marker. Context goes through
security scanning; inspect the loaded result if content appears absent rather
than assuming every instruction reached the model.

`--ignore-rules` is a diagnostic isolation option, not a remedy for missing
business instructions; it also disables SOUL identity and other user setup.
Confirm its exact scope in the installed CLI before use.
