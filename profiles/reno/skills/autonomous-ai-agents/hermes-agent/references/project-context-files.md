# Project Context Files

Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
For version-sensitive behavior, inspect `agent/prompt_builder.py` in the installed
Hermes tree; local installation paths are defined in the profile's `.hermes.md`.

## Discovery and responsibilities

Hermes selects one project context type, using the first matching type below.
SOUL.md is loaded independently from `$HERMES_HOME/SOUL.md` as agent identity.

| Context type | Discovery in the installed loader |
|---|---|
| `.hermes.md` / `HERMES.md` | Nearest match from the working directory upward to the Git root; parent files are not merged. |
| `AGENTS.override.md` / `AGENTS.md` / `agents.md` | Inside a Git repository, merge the directory chain from root to working directory. In each directory, the first matching name wins. Outside a repository, check only the working directory. |
| `CLAUDE.md` / `claude.md` | Working directory when no higher-priority type matched. |
| `.cursorrules` / `.cursor/rules/*.mdc` | Working directory when no higher-priority type matched. |

During execution, subdirectory discovery can inject additional project context
when paths are accessed. This is distinct from startup discovery; inspect
`agent/subdirectory_hints.py` for its supported names and limits.

Use SOUL.md for identity, tone and permanent behavioral boundaries; project
context for environment and conventions; skills for reusable procedures. A
profile's SOUL is independent of the current working directory. A profile-local
`.hermes.md` requires the effective working directory to resolve to that context.
Do not assume it is loaded merely because it sits beside config.yaml.

## Size and scanning

An explicit positive `context_file_max_chars` sets the per-file cap. Otherwise
startup loading uses a dynamic cap based on the model context window, with a
20,000-character floor and 500,000-character ceiling. An unknown context window
uses the floor. Oversized files are truncated using head and tail portions;
check the actual loader output instead of assuming every long file is cut.

The context scanner replaces the affected file's entire content with a
`[BLOCKED: ...]` placeholder when it detects a threat. It does not merely remove
the offending sentence. Check both blocking and truncation after editing.

## Diagnosis

Use the installed `load_soul_md` and `build_context_files_prompt` loaders with
the profile home, effective working directory and actual context length to
inspect loading. Avoid printing confidential context or configuration values.
`hermes --ignore-rules` is an isolation mode that skips more than project files;
inspect its current CLI behavior before using it as a diagnostic, and do not
mistake an isolated session for a faithful test of the configured profile.
