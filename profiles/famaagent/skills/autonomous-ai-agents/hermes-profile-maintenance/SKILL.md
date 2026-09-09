---
name: hermes-profile-maintenance
description: "Use when maintaining a Hermes profile or saving verified, reusable learning in its memory and skills."
version: 1.1.0
author: FamaAgent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, profile, configuration, verification, gateway, testing]
---

# Hermes Profile Maintenance

Use the maintenance procedure for explicit maintenance of a Hermes profile: configuration,
profile-local runtime behavior, gateway lifecycle, memory/skills capability
checks, and tests of changes. Keep the change minimal, reproducible, and
verifiable.

The learning section also applies after ordinary tasks and corrections; it
does not require a separate administrative request. Authorization and limits
come from `SOUL.md`, not from this skill.

## Procedure

1. Load the authoritative Hermes operating guidance before changing Hermes. Confirm the target profile and the exact component in scope.
2. Inspect the current resolved values with `hermes -p <profile> config get <key>` and check the relevant runtime status before editing. Preserve existing platform allowlists, toolsets, MCP boundaries, and unrelated settings.
3. Change `config.yaml` only through the native commands:
   `hermes -p <profile> config set <key> <value>` or
   `hermes -p <profile> config unset <key>` to remove an obsolete key.
   Never rewrite `config.yaml` directly with a file editor, because native updates preserve Hermes' parsing and versioning behavior.
   For other authorized text files, use `read_file`, `write_file` or `patch`;
   use `skill_manage` for skills. Respect runtime refusals and approval requirements.
4. Read back every changed key, then run `hermes -p <profile> config check`. Treat the check as necessary but not sufficient: also query the component-specific status command and exercise the affected execution path.
5. For development tests, use the project's supported environment and dependency declaration. If a runtime service environment lacks a development-only runner, invoke it through the project runner (for example, `uv run --extra dev pytest ...`) rather than changing the service environment just to run tests.
6. If a gateway reload or restart is needed, perform it from an external operator shell. Do not attempt to restart the gateway from a process running inside that same gateway, and do not bypass Hermes' refusal; verify that the service remains active after any refused or completed lifecycle action.
7. Report what changed, the affected files/components, the exact validation commands and real results, and any remaining reload or operational limitation. Never include secrets or unnecessary identifiers.

For configuration changes, read
[`references/configuration-verification.md`](references/configuration-verification.md)
for the native commands, platform authorization checks and lifecycle verification.

## Persistent learning and skills

- After a task, correction or proven reusable procedure, evaluate whether there
  is durable learning. In short workers, save it before the final answer and
  task closure; background review complements foreground learning.
- Find existing coverage with `skills_list` and read it with `skill_view`.
  Prefer updating an existing skill. Create a new class-level skill only for
  a genuinely new task class, with prerequisites, proven steps, pitfalls and
  verification criteria. Verify the write result and read it back.
- Write only to this profile's own memory and skills. Generalize the lesson;
  do not persist third-party PII, secrets, raw conversations, temporary client
  state or unverified hypotheses. Do not delete skills or change commercial
  policies as a learning action. No durable lesson means no write is needed.
- Keep built-in memory and user profile enabled when the requested behavior is persistent learning.
- Keep the `memory` and `skills` toolsets available on the intended platform when the profile must learn across sessions.
- Keep `memory.write_approval` and `skills.write_approval` aligned with the requested consent model; automatic learning requires writes not to be silently staged.
- Enable the profile's background self-improvement review when automatic memory and procedural-skill capture is requested.
- Treat curator pruning/consolidation as a separate lifecycle concern; do not enable broad LLM consolidation merely to turn on per-session learning.
- Store stable user facts, preferences, and cross-task environment invariants in memory; store reusable procedures, decision points, pitfalls, and verification criteria in a class-level skill.
- Before editing an existing skill, read its current `SKILL.md` (and any support file being overwritten) with `skill_view`; patch the existing class-level rule in place, strengthen duplicates instead of appending them, and prefer a topical reference over a session-specific skill.
- Treat `memory.nudge_interval` as a user-turn count and `skills.creation_nudge_interval` as a tool-iteration count; do not compare or tune them as if they used the same unit.
- Require a final, uninterrupted response and the necessary write tools before relying on the native review fork; a configured interval alone does not prove that a review will run or persist.
- For one-shot CLI runs, do not assume daemon threads finish before process exit; use the official session-finalization hook to await background review with a bounded timeout (the local lifecycle plugin uses up to 300 seconds), while keeping gateway-channel reviews asynchronous according to their lifecycle contract.
- Validate persistence by exercising the real write path and recovering the memory or skill from an independent process; also verify channel isolation and the wait bound when lifecycle behavior is involved.
- Do not manufacture a skill during validation. Save only a generalizable workflow or preference that a future session can reuse.

## Safety and evidence rules

- Preserve security boundaries and unrelated channel capabilities while changing a profile.
- Never copy secrets from configuration, environment files, auth stores, or logs into a report or skill.
- Distinguish a failed command from a failed capability; retry through a documented supported path before concluding that the feature is unavailable.
- Do not convert setup-state failures, one-off transcripts, or unresolved attempts into durable guidance. Capture the working alternative and the reason it is the reliable path.
- Prefer extending this class-level skill or one of its topical references over creating a narrow incident skill.
