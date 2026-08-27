# Platform toolsets and session-store audits

Use this note when reducing a messaging platform's authority or counting its
sessions without exposing message bodies or participant identifiers.

## Root profile versus named profiles

For the default/root profile, remove an ambient profile override and omit `-p`:

```bash
env -u HERMES_HOME hermes config get platform_toolsets.<platform>
env -u HERMES_HOME hermes tools list --platform <platform>
```

For named profiles, use `hermes -p <profile> ...`. Audit unrelated platform
entries before and after a narrow change so a serializer or broad edit does not
silently alter control channels or CLI authority.

## Verifying a platform-toolset reduction

Use all three evidence layers:

1. `config get platform_toolsets.<platform>` proves the persisted selection.
2. `tools list --platform <platform>` proves the surface resolved by a fresh CLI
   invocation.
3. The existing gateway/session remains a separate fact because its schemas may
   be cached until reset or restart.

A `config set platform_toolsets.<platform> ...` invocation may warn that the key
is not recognized by the config schema even when the installed runtime reads it.
Do not dismiss the warning or assume failure. Check the persisted value, run
`config check`, and require the post-change platform manifest to demonstrate the
intended enable/disable result.

`hermes tools list` prints configurable built-in and plugin toolsets. It can omit
valid non-configurable toolsets such as `kanban`; omission from this display is
not proof of disablement. Confirm such a toolset through `config get`, then trace
`hermes_cli/tools_config.py` and `toolsets.py` when the distinction affects an
acceptance criterion.

For a least-privilege change, verify every forbidden high-authority toolset
individually (terminal, file access, code execution, browser/computer control,
delegation, cron, and session search as applicable), not merely the presence of
the intended allowlist.

## Safe session-store counting

Open the database read-only and inspect structure before querying:

```python
import sqlite3
c = sqlite3.connect("file:/root/.hermes/state.db?mode=ro", uri=True)
for table in ("sessions", "messages"):
    print(list(c.execute(f"PRAGMA table_info({table})")))
    print(list(c.execute(f"PRAGMA foreign_key_list({table})")))
```

In the schema observed in this runtime, the relation is
`messages.session_id -> sessions.id`; platform identity is on
`sessions.source`, not on `messages`. Count without selecting participant or
content fields:

```sql
SELECT COUNT(DISTINCT s.id),
       COUNT(m.id),
       MIN(m.timestamp),
       MAX(m.timestamp)
  FROM sessions AS s
  LEFT JOIN messages AS m ON m.session_id = s.id
 WHERE lower(s.source) = lower(?);
```

The `LEFT JOIN` preserves platform sessions that contain zero messages. Convert
non-null message timestamps from Unix epoch to explicit UTC. If no matching
session exists, report zero sessions/messages and “sem mensagens” for both dates;
do not fabricate dates from unrelated session activity.

Privacy rules:

- Never select or print `content`, `user_id`, `chat_id`, `session_key`,
  `display_name`, or `origin_json` for a count-only audit.
- Listing distinct `source` values and aggregate counts is safe when needed to
  validate the platform label.
- A failed query whose exception handler substitutes an empty result does not
  prove zero sessions; inspect the schema and issue a corrected read-only query.
