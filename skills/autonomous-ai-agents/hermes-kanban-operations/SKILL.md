---
name: hermes-kanban-operations
description: "Use when configuring or verifying Hermes Kanban settings."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, kanban, dispatcher, gateway, configuration, verification]
---

# Hermes Kanban Operations

Use this skill for durable configuration changes to Hermes' Kanban work queue, especially dispatcher placement, scheduling, orchestration, concurrency, and notification behavior.

## Workflow

1. Load the Hermes Agent guidance and the Kanban/background-systems reference before changing settings. The bundled `hermes-agent` skill is protected; do not patch it. This class skill carries the Kanban-specific operational procedure.
2. Discover the active profile home from `$HERMES_HOME` (fall back to `~/.hermes`) and use `hermes config path`; do not assume another profile's configuration.
3. Inspect current values with `hermes config get kanban` or targeted `hermes config get kanban.<key>` calls. Confirm the requested semantics before writing.
4. Apply settings with `hermes config set kanban.<key> <value>`, not by hand-editing YAML. Use `--force` only for a documented/implemented key that the installed CLI does not advertise in its defaults.
5. Do not restart the gateway unless the user explicitly asks. Configuration changes that are read by the embedded dispatcher should be left for its normal live behavior.
6. Verify the result from the actual configuration file, not only from command output or in-memory assumptions. Read the path returned by `hermes config path` and extract the saved `kanban:` values.
7. Report exactly the requested fields, one per line when requested, preserving booleans and numeric values as stored. Mention the file path and whether a restart was performed only if useful.

## Key semantic mappings

- `kanban.dispatch_in_gateway`: dispatcher runs inside the gateway.
- `kanban.auto_decompose`: automatic triage decomposition; `false` leaves routing/decomposition to the human.
- `kanban.auto_subscribe_on_create`: automatic task subscription at creation.
- `kanban.dispatch_interval_seconds`: seconds between dispatcher cycles.
- `kanban.failure_limit`: consecutive spawn failures before auto-blocking.
- `kanban.review_dispatch`: automatic review-lane dispatch.
- `kanban.max_in_progress`: board/host-wide running-task cap.
- `kanban.max_spawn`: per-dispatch-cycle spawn budget in the installed Kanban implementation; distinguish this from the running-task cap.

## Pitfalls

- Do not confuse `max_in_progress` (simultaneous running tasks) with `max_spawn` (new workers spawned by one dispatcher pass).
- Do not silently enable `auto_decompose` when the user wants manual control.
- Do not report the CLI's “Set …” lines as verification; reread the YAML.
- Do not normalize or omit explicit `false`, `0`, or `null` values when reporting requested settings.

## Reference

- See `references/kanban-config-verification.md` for the verified key mapping and a concise verification pattern from a real configuration task.
