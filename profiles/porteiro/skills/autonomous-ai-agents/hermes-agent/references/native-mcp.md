# Native MCP Client

Use for configuring MCP server connections and verifying platform exposure.
Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
Use the installed runtime to resolve version differences.

## Configuration

The standard Hermes install includes MCP support. Servers live under
`mcp_servers` in the active profile config.yaml. Use the native config CLI;
credentials stay in the profile secret store and are referenced with `${VAR}`.
A server uses either `command`/`args` for stdio or `url` for HTTP.

```yaml
mcp_servers:
  example:
    url: https://example.invalid/mcp
    headers:
      Authorization: Bearer ${EXAMPLE_TOKEN}
    tools:
      include:
        - lookup_record
    resources: false
    prompts: false
```

`tools.include` is an allowlist of original server tool names. `tools.exclude`
can suppress tools; avoid exposing every tool when a specialist needs one.
Resource and prompt wrappers are controlled independently. Tool names exposed
to the agent normally use `mcp_<server>_<tool>`; inspect the actual catalog.

For stdio servers, use `env` to pass the required credentials explicitly. Do not
assume every variable in the host shell is inherited. For HTTP, headers support
environment references; verify resolution without printing secret values.
Kanban task/run headers require the matching worker context; ordinary CLI
invocations do not prove the worker-scoped identity capability works.

## Platform exposure

Configured servers are not necessarily exposed on every platform.
`platform_toolsets.<platform>` can select servers; the `no_mcp` sentinel disables
MCP exposure for that platform. With no explicit server allowlist and default
MCP inclusion enabled, the resolver adds enabled configured servers.

For verification, call the installed
`hermes_cli.tools_config._get_platform_tools(config, platform,
include_default_mcp_servers=True)`. `hermes tools list --platform ...` alone is
not proof of MCP exposure: it may enumerate configured servers independently
of the platform resolver. Inspect server filters as a separate check.

## Reload and runtime evidence

`mcp.auto_reload_on_config_change` controls automatic config-change reload.
When false, do not claim an existing process adopted edits. Use the supported
lifecycle mechanism only when in scope, and distinguish configuration reads,
fresh-process discovery, and a running gateway's connections. Avoid the obsolete
blanket claim that Hermes has no MCP reload support.

Check `hermes mcp --help` for catalog/configure/login commands in the installed
version. Connection discovery proves availability, not success of the business
lookup. Only call a real tool when the task warrants it; test fixtures should
not contact external services.

## Failures

Check the profile, transport, server filters, platform selection, credential
presence (not value), and sanitized connection errors. Missing tools or failed
identity resolution are capability failures; do not widen filters or use an
unapproved backend as an implicit fallback.
