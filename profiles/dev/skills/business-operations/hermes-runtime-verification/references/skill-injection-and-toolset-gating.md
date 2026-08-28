# Skill loading and toolset gating in the installed Hermes runtime

This note captures the source-level distinction between the normal skill index,
tool schemas, and explicit skill loading. Re-check line numbers after a Hermes
update; the installed tree is the authority.

## Automatic system-prompt index

`/usr/local/lib/hermes-agent/agent/system_prompt.py` builds the normal skill
index only when `agent.valid_tool_names` contains at least one of
`skills_list`, `skill_view`, or `skill_manage` (`:524-553`). If none is present,
it assigns `skills_prompt = ""`; the profile's local `skills/` directory is not
indexed into the normal prompt.

The helper it would call,
`/usr/local/lib/hermes-agent/agent/prompt_builder.py:1739-1800`, resolves an
explicit profile skills directory when supplied and then scans/indexes it. That
helper is therefore not evidence that scanning happens for every session: the
caller-side gate in `system_prompt.py` decides whether it is called.

## Toolset filtering

`/usr/local/lib/hermes-agent/model_tools.py:323-346` documents that all tools
must belong to a toolset and that `enabled_toolsets` limits the definitions
returned to the model. The filtering loop is at `:417-464`.

The native skill tools are registered under the `skills` toolset:

- `tools/skills_tool.py:2017-2024` — `skills_list`;
- `tools/skills_tool.py:2180-2185` — `skill_view`;
- `tools/skill_manager_tool.py:1857-1861` — `skill_manage`.

Thus a profile whose effective platform toolsets omit `skills` normally has no
skill-tool schemas and consequently no automatic skill index.

## Explicit preload is a separate path

A launch-time preload is not the same as the normal index. In
`/usr/local/lib/hermes-agent/agent/skill_commands.py:839-904`,
`build_preloaded_skills_prompt()` loads requested payloads directly, formats
full skill content, and returns prompt text. It checks the configured disabled
skill names (`:858-880`) but does not use the agent's `valid_tool_names` gate.

`/usr/local/lib/hermes-agent/cli.py:8349-8394` joins that returned text into the
CLI system prompt. Therefore `hermes -s <name>` can be an explicit exception to
the statement that the `skills` toolset disables automatic prompt injection.
Do not claim universal inaccessibility without checking this path.

Gateway slash-skill commands also have a dedicated path: see
`/usr/local/lib/hermes-agent/gateway/run.py:18377-18454`, which resolves skill
commands and builds the invocation message before normal message processing.
Per-platform disabled-skill checks are performed there. Toolset disablement and
configured disabled skills are separate controls.

## Profile isolation

`/usr/local/lib/hermes-agent/agent/system_prompt.py:276-317` resolves the
agent's own profile home and its `<home>/skills` directory. The normal builder
passes that directory as `skills_dir_override` (`:546-551`). When investigating
profile leakage, verify this agent-home resolution rather than trusting ambient
`HERMES_HOME` alone.

## Audit recipe

For a read-only profile audit:

1. Run `hermes -p <profile> config check` and record the exit code.
2. For native toolsets, run `hermes -p <profile> tools list --platform
   <platform>` and treat it as evidence for a new invocation, not an existing
   cached session. For MCP servers, that command is not evidence: it enumerates
   every configured `mcp_servers` entry without consulting per-platform
   resolution. Prove MCP exposure with
   `_get_platform_tools(config, platform, include_default_mcp_servers=True)`, the
   same default used by the gateway.
3. For a secret-bearing `config get`, retain only safe structure (server name,
   URL, header key) and replace the value with `[valor omitido]`.
4. Select the latest matching gateway log entries, not merely the first match.
5. Cite the installed source paths and lines for non-obvious conclusions.
6. Confirm `/root/.hermes` and `/usr/local/lib/hermes-agent` integrity when the
   audit is explicitly read-only; do not create a commit.
