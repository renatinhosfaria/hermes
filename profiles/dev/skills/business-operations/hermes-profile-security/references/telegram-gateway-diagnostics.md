# Telegram Gateway Diagnostics Reference

This reference records reusable findings from a Hermes profile security audit.
It deliberately omits live IDs, tokens, invite links, message bodies, and other
profile-specific values.

## Configuration paths

- `platforms.telegram.home_channel` controls the configured Telegram home
  channel and topic/thread routing.
- In the installed runtime, Telegram authorization is evaluated from the
  adapter's `allow_from` and group restriction values exposed through the
  `telegram` configuration namespace.
- A root-level `TELEGRAM_ALLOWED_USERS` entry is not the adapter configuration
  path. `hermes config set` can still persist an unrecognized custom key and
  bridge it to `.env`, so audit both locations by count and remove the stale
  YAML root entry when the documented adapter keys are present.

## Toolset resolution finding

`hermes_cli/tools_config.py::_get_platform_tools()` resolves
`config["platform_toolsets"][platform]`. It does not use the top-level
`config["toolsets"]` list to scope a messaging platform. Therefore:

1. A top-level `toolsets` list can look correct in `config.yaml` while the
   Telegram gateway still exposes the default/full platform toolsets.
2. For native toolsets, use `hermes -p <profile> tools list --platform telegram`
   as evidence. For MCP servers, do **not** use it: the command enumerates every
   configured `mcp_servers` entry without consulting per-platform resolution, so
   it can show a server that Telegram does not expose.
3. Prove MCP exposure only with
   `_get_platform_tools(config, "telegram", include_default_mcp_servers=True)`,
   the same default used by the gateway.
4. If the applicable check contradicts the requested least-privilege set,
   report the mismatch and correct the platform-specific configuration rather
   than claiming the top-level list worked.

The non-interactive command form is important: bare `hermes tools` opens an
interactive configuration UI and may fail when run without a TTY.

## Config migration and layered toolset semantics

- `hermes -p <profile> config check` can report `Config version: 38 → 39`
  without persisting the migration. Use the explicit mutating command
  `hermes -p <profile> config migrate` when the owner authorized migration.
- The repository root is a separate Hermes home: run
  `HERMES_HOME=/root/.hermes hermes config migrate` for its `config.yaml`, and
  run the profile form for each profile that must be migrated. Before committing,
  compare `git status --porcelain`, `git diff --name-only`, and the complete diff;
  only the known migration files may be staged.
- A migration can materialize comments/defaults and bump `_config_version` even
  when no literal `bfl` or `video_generate` entry exists in the saved config.
  Do not infer extra semantic changes from the migration banner alone.
- The root `toolsets` list is not simply ignored: the Kanban gate can inspect it
  for worker capability checks such as the presence of `kanban`. Messaging
  platform scope is resolved from `platform_toolsets.<platform>` by
  `_get_platform_tools`. Preserve the root list when the Kanban architecture
  depends on it, and configure Telegram/CLI platform scope separately.
- In Hermes 0.20.5, `_RECENTLY_SHIPPED_TOOLSETS` is empty and `bfl` is retired;
  migration 38→39 removes saved `bfl` entries. Credential-based autoactivation
  (for example xAI `x_search` and Home Assistant) is a separate code path. Do
  not report an active `bfl` autoactivation without checking the installed
  source and resolving `toolsets.TOOLSETS`.

## Restart and log evidence

- Gateway dispatcher log entries are append-only evidence. Inspect the most
  recent matching entries and distinguish a historical dispatcher-lock message
  from a newer `disabled via config kanban.dispatch_in_gateway=false` message.
- Persisted config and active process state are separate facts. A config write
  does not prove that the running gateway has reloaded it.
- To inspect whether a running process inherited an environment variable, count
  matching entries in `/proc/<PID>/environ`; never print the values. A zero
  count describes the process environment only and does not prove that Hermes
  has not loaded `.env` internally.
- If the user owns the restart, do not restart the gateway. Report the
  persisted state and explicitly state that activation is pending restart.

## Safe Telegram diagnostic rules

- Never call `getUpdates` against a bot whose gateway is long-polling.
- Authenticate API calls from the protected profile `.env` without printing the
  token or interpolated URL.
- For `.env`, report only occurrence counts; do not print matching lines.
- Request only the chat metadata and member/admin data needed for the audit;
  do not include invite links or unrelated permissions in the report.
