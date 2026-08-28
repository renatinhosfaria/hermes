# Gateway session reset and privacy-preserving audits

Use this note when an operator needs to understand or prepare a gateway-session
reset without deleting its transcript, especially for WhatsApp or another
contact-addressed platform.

## Trace the supported reset path

Audit the installed source; line numbers are version-sensitive and must be
re-read before reporting.

1. Resolve `/new` and its `/reset` alias in `hermes_cli/commands.py`.
2. Follow gateway dispatch in `gateway/run.py` to the reset handler.
3. In `gateway/slash_commands.py`, verify that the handler derives the current
   `session_key` from the inbound `SessionSource` and calls
   `async_session_store.reset_session(session_key)`.
4. In `gateway/session.py`, inspect `SessionStore.reset_session` and establish
   separately that it:
   - reuses the same `session_key`;
   - generates a fresh `session_id`;
   - passes the predecessor ID as `parent_session_id` and `_reset_from`;
   - repoints only the routing entry for that key.
5. Follow every DB method called by reset into `hermes_state.py`. A reset should
   end/promote the predecessor row and insert the child row. Confirm that this
   path does not delete or rewrite predecessor messages. Do not infer deletion
   from UI wording such as “discard history”: that can mean “do not load old
   context into the new agent” while the transcript remains durable.
6. Verify CLI support independently with live `hermes sessions --help` and the
   sessions parser. An interactive `/reset` is not the same as an administrative
   `hermes sessions reset` subcommand.

When the request explicitly says not to reset yet, do not exercise the live
handler. Source tracing plus read-only database evidence is the correct test.

## Prove caller scoping and command authority

Treat these as independent controls:

1. **Platform intake:** `dm_policy`, `allow_from`, pairing, and allow-all settings
   decide whose messages reach the gateway.
2. **Gateway authorization:** inspect the effective allowlist/allow-all path;
   `dm_policy: open` alone may not establish authorization.
3. **Slash-command policy:** `allow_admin_from` enables the extra command gate;
   when absent, backward-compatible behavior may let every otherwise-authorized
   user run registered slash commands.
4. **Conversation targeting:** inspect platform event construction and
   `build_session_key`. For contact-addressed DMs, the key must include the
   caller's chat/contact identity. Confirm the reset handler accepts no target
   session argument; `/new <text>` may use that text only as a title.

Only after all four layers are proven may the audit conclude that a stranger can
reset their own session but not another contact's. Re-check canonicalization and
alias handling for platforms such as WhatsApp so one person's equivalent JID/LID
forms intentionally converge without collapsing distinct contacts.

## Effective configuration without secret or PII leakage

- Read only the exact access-control keys needed for the claim.
- For `.env`, emit classifications such as `present`, `truthy`, `entry_count`, or
  `has_wildcard`; never print raw values or neighboring lines.
- `/proc/<pid>/environ` can omit values loaded into process memory from dotenv
  after exec. Absence there is not proof that runtime-scoped secret/config
  loaders cannot see a value. Corroborate with the installed loader path, a safe
  config check, and focused raw-file classification.
- Separate persisted configuration, loader resolution, and running-process state
  in the report.

## Safe session inventory

Do not use `hermes sessions list` for a privacy-constrained inventory: it renders
session titles and message previews even when filtered by source.

Instead:

1. Open the target `state.db` with SQLite URI `mode=ro`.
2. Inspect `PRAGMA table_info(sessions)` and `PRAGMA table_info(messages)`.
3. Join `messages.session_id` to `sessions.id` and filter on
   `lower(sessions.source)`.
4. Select only fields explicitly authorized by the operator. For a reset audit,
   this may include `sessions.id AS session_id`, `started_at`, and
   `COUNT(messages.id)`; never select contact numbers, `session_key`, `chat_id`,
   `user_id`, content, title, preview, display name, or `origin_json`.
5. Use `LEFT JOIN` so zero-message sessions remain visible, and convert epochs to
   explicit UTC.
6. Repeat the same read-only query at closeout when proving no reset or mutation
   occurred. Live traffic can still change counts, so distinguish concurrent
   activity from audit writes.

Example query shape:

```sql
SELECT s.id, s.started_at, COUNT(m.id)
  FROM sessions AS s
  LEFT JOIN messages AS m ON m.session_id = s.id
 WHERE lower(s.source) = lower(?)
 GROUP BY s.id, s.started_at
 ORDER BY s.started_at;
```

## Audit post-reset Kanban activity without leaking contact data

The human-readable `hermes kanban list` is priority-sorted by default, not a
reliable creation timeline. For an incident window, use
`hermes -p <profile> kanban list --json --sort created-desc`, parse the JSON
locally, and emit only task ID, creation time, assignee, status, and completion
time. Do not print `body`, title, session ID, comments, or raw metadata when they
may contain a phone number or conversation text. Avoid sending the complete JSON
to a terminal capture: even if the final report is sanitized, tool output can
still expose PII and create a long cache artifact.

For each task inside the time window, inspect only that task with
`hermes kanban show <id> --json` and distinguish:

- `task.result`, which may be null;
- `latest_summary`, which can still describe a blocked/completed outcome;
- `runs[].metadata.response_ready`, whose key may be absent, null, or populated;
- `completed_at`, which is null for a blocked task even when the worker run has
  an `ended_at` timestamp.

Do not report “time to completion” when the last task is blocked. Report it as
undefined and, if useful, separately label creation-to-block or
creation-to-worker-end. A blocked first-stage task also means downstream
assignees were not reached; do not substitute an older unrelated task for a
missing downstream card.

## Verify per-platform display settings

A log search returning no `tool_progress` lines is only supporting evidence. To
prove the effective mode:

1. target the serving profile explicitly (`hermes -p <profile>`), because the
   ambient `HERMES_HOME` may point at the auditor's profile;
2. read the safe scalar global and per-platform keys;
3. run the installed `gateway.display_config.resolve_display_setting` against
   that profile's raw config and print only the resolved value;
4. cite the resolver's precedence and normalization code.

This distinguishes an actual per-platform `false` → `off` override from silence
caused by a turn that happened not to emit progress.

## Trace reset banners and home-channel notices

For `/new` or `/reset`, inspect `gateway/slash_commands.py` and the helper that
formats session information. In the observed implementation, the handler always
resolves model/provider/context, appends a random tip, and returns the combined
text as an `EphemeralReply`; absence of a documented branch or config gate must
be confirmed in current source before saying the banner can be reduced.

Trace home-channel onboarding separately in `gateway/run.py`. The notice is
gated by empty session history plus absence of a configured home channel. Text
such as “ignore to skip” does not necessarily persist a suppression preference;
a reset can make the notice eligible again. Before claiming suppression is
possible, find an explicit persisted setting in the current resolver.

`display.ephemeral_system_ttl` is not equivalent to suppression. Verify whether
it is global or per-platform and whether the adapter overrides
`delete_message`; unsupported adapters force the TTL to zero. For WhatsApp
Baileys home targets, cite `gateway/whatsapp_identity.py`: preserve a fully
qualified inbound JID (`<digits>@lid`, `<digits>@s.whatsapp.net`, or
`<group-id>@g.us`) and never print the real contact identifier in the report.

## Audit WhatsApp LID-to-phone identity flow

When a downstream worker says the phone was missing, distinguish what reached
the bridge, what the gateway retained, what became model-visible prompt text,
and what remained recoverable only inside runtime state.

1. Trace the Node bridge from `msg.key.remoteJid` and
   `msg.key.participant || chatId` into its emitted `chatId`, `senderId`,
   `senderName`, and `chatName` fields.
2. Trace the Python adapter's `build_source(...)` call. In the native WhatsApp
   adapter, `chatId` becomes `SessionSource.chat_id`, `senderId` becomes
   `user_id`, and no separate `user_id_alt` is populated unless current source
   proves otherwise. For a LID DM, both `chat_id` and `user_id` can therefore be
   the same `<digits>@lid` value.
3. Follow `build_session_context_prompt`, not merely the `AIAgent` constructor.
   Identity fields passed into the agent or bound as `HERMES_SESSION_*`
   ContextVars are runtime/tool context, not automatically provider-visible
   text. The session prompt normally renders `user_name` first and falls back to
   `user_id`; `user_id_alt` has no independent prompt line. `chat_id` can still
   surface in group/fallback/origin labels when a display name is absent.
4. Reconstruct the deterministic session-context render from the stored
   `origin_json` only when the operator authorizes that row. Emit booleans such
   as `contains_lid`, `contains_mapped_phone`, and `contains_user_name`; never
   print the values. Do not use `sessions.system_prompt` absence as proof that
   the provider did not receive gateway context—the gateway appends this block
   as an ephemeral system prompt.
5. Open `state.db` and `kanban.db` with SQLite URI `mode=ro`. Classify
   `sessions.chat_id`, `sessions.user_id`, `origin_json`, and
   `kanban_notify_subs.{chat_id,user_id,user_id_alt}` by shape only. Scan all
   authorized row columns locally for the resolved phone and emit column names,
   not values. This catches the non-obvious case where raw routing fields retain
   LID while canonical `session_key` embeds the mapped phone.
6. Resolve aliases under the target profile's `HERMES_HOME` with the public
   Python `expand_whatsapp_aliases()`. It returns normalized aliases, not a typed
   phone result. `canonical_whatsapp_identifier()` chooses the shortest alias
   and likewise does not promise “phone.” To identify the phone without guessing,
   verify the bridge convention: `lid-mapping-<phone>.json` maps phone→LID and
   `lid-mapping-<lid>_reverse.json` maps LID→phone. Report only existence,
   alias count, and equality/classification assertions. Re-check the installed
   tree before claiming no dedicated public `lid_to_phone` helper exists; the JS
   bridge may have a private reverse-map builder while Python exposes only alias
   expansion.
7. For a blocked Kanban task, parse `hermes -p <profile> kanban show <id> --json`
   locally and print only the explicitly requested body/result fields after
   digit masking. Read the latest `blocked` event's `payload.kind`; do not infer
   `block_kind` from the human-readable reason, and never unblock during a
   read-only audit.

Report the boundary explicitly: “phone recoverable by runtime” does not imply
“phone visible to the model,” and “phone present inside canonical session_key”
does not imply it was copied into a Kanban card or notifier subscription.

## Reporting checklist

- State the exact supported command and whether a gateway-targeting CLI exists.
- Cite current installed file:line ranges for every identity/lineage claim.
- Explain context discontinuity versus transcript persistence explicitly.
- List only the operator-authorized session metadata.
- State intake authorization, slash authorization, and session-key isolation as
  separate conclusions.
- Confirm no reset, restart, state write, or platform-session deletion occurred.
