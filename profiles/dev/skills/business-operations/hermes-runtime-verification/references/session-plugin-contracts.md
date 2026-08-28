# Session, plugin, and tool-handler source audits

Use this reference when a plugin specification depends on exact runtime contracts. The paths and semantics below were verified against Hermes Agent 0.20.5; line numbers and implementation details must be re-checked in the installed source on every audit.

## Session history primitives

- `hermes_state.py`: `SessionDB.get_messages(...)` supports both `include_inactive` and `include_compacted`.
- Storage states are encoded by two columns:
  - live: `active=1`;
  - archived by in-place compaction: `active=0, compacted=1`;
  - removed by rewind/undo: `active=0, compacted=0`.
- `include_compacted=True` returns live plus compacted rows while excluding rewind rows; `include_inactive=True` returns every state.
- `SessionDB(db_path: Path = None, read_only: bool = False)` has a real read-only API. The read-only branch opens SQLite with `file:<path>?mode=ro` and skips schema initialization.
- The state schema version is defined in `hermes_state_common.py`, not necessarily in `hermes_state_schema.py`.

## Typed internal transcript rows

- Gateway self-injected events are persisted as role `user` with `display_kind="internal_notification"`.
- The literal is assigned in `gateway/run.py`, carried through `gateway/session.py`, and written to `messages.display_kind` by `SessionDB`.
- Do not describe the whole message as removed from model history: `agent/conversation_loop.py` strips the display metadata from provider-bound copies, while `agent/context_compressor.py` excludes typed display rows from human-turn/actionability predicates. These are different filters.

## Profile plugin discovery and symlinks

- User plugin discovery starts at `get_hermes_home() / "plugins"` in `hermes_cli/plugins.py`.
- The scanner uses `Path.iterdir()` followed by `Path.is_dir()` and does not reject `is_symlink()`. On supported Python versions, `Path.is_dir()` follows symlinks by default, so a profile plugin directory symlink is discovered if its target contains a valid manifest.
- Framework-owned isolation is profile-scoped:
  - `PluginManager.scope_key` is the resolved Hermes home;
  - tool registry overlays are keyed by that scope;
  - `ctx.state`/`PLUGIN_DATA` lives under the profile's `plugin-data/`;
  - duplicate imports receive profile-safe module namespaces.
- Qualify the guarantee: a plugin that writes beside its shared source tree or uses an external backend without a profile namespace can still conflict across profiles.

## General plugin tool-handler contract

- `PluginContext.register_tool(...)` accepts a callable handler.
- Registry invocation is `handler(args: dict, **kwargs)`.
- For ordinary tools, the current dispatcher passes `task_id`, `session_id`, and `user_task`; `execute_code` receives `enabled_tools` instead of `user_task`.
- `current_session_id` is not a general handler kwarg. `session_search` is agent-loop-special and receives `agent.session_id` directly in `agent/agent_runtime_helpers.py`.
- A plugin handler should normally read the current session from `kw.get("session_id")`.
- Resolve profile identity through `get_hermes_home()` or `hermes_cli.profiles.get_active_profile_name()` rather than a model argument.
- Detect a Kanban worker from `HERMES_KANBAN_TASK`; related authoritative process fields include `HERMES_KANBAN_RUN_ID`, `HERMES_KANBAN_CLAIM_LOCK`, and `HERMES_SESSION_SOURCE=kanban`.

## Plugin toolsets by platform

- `hermes_cli/tools_config.py::_get_platform_tools(config, platform)` reads only `platform_toolsets.<platform>` for the current surface.
- Plugin toolset keys are merged into the explicit known-key set, so the same profile may list a plugin toolset for WhatsApp and omit it for Telegram.
- Trace the gateway call into `_get_platform_tools`; configuration text alone is not proof of effective resolution.

## Reporting discipline

1. Quote complete signatures/docstrings when explicitly requested.
2. Cite absolute `file:line-range` locations and include the controlling branch, not only comments.
3. Distinguish framework guarantees from plugin-author behavior.
4. For negative claims, search the full installed tree and say `não existe nesta versão` only after checking aliases and special dispatch paths.
5. Close strict read-only audits with clean Git status checks for both the installation and `/root/.hermes`; do not commit when the task expressly forbids it.
