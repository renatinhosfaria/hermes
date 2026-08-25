# Kanban configuration verification

## Verified mapping

| User-facing setting | Saved key | Example final value |
|---|---|---:|
| Dispatcher inside gateway | `kanban.dispatch_in_gateway` | `true` |
| Automatic decomposer | `kanban.auto_decompose` | `false` |
| Subscribe on task creation | `kanban.auto_subscribe_on_create` | `true` |
| Dispatcher cycle interval | `kanban.dispatch_interval_seconds` | `30` |
| Spawn-failure block threshold | `kanban.failure_limit` | `2` |
| Automatic review dispatch | `kanban.review_dispatch` | `false` |
| Simultaneous running tasks | `kanban.max_in_progress` | `4` |
| New workers per dispatcher cycle | `kanban.max_spawn` | `2` |

## Verification pattern

1. Run `hermes config path` to resolve the active profile's YAML.
2. Apply each requested setting with `hermes config set kanban.<key> <value>`.
3. If a key is implemented but absent from the installed defaults/CLI schema, use `--force` for that key only; do not use hand edits.
4. Read the YAML back and inspect the `kanban:` mapping. Report the exact serialized values, not merely the success messages from `config set`.

## Important distinction

`max_in_progress` limits currently running tasks. `max_spawn` is the installed dispatcher implementation's per-pass budget for new worker spawns. They are separate controls and may both need to be set.
