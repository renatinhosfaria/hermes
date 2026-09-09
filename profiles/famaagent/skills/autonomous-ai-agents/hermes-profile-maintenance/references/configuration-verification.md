# Configuration and verification recipe

Use this recipe after a profile configuration change.

## Native update and readback

```bash
hermes -p <profile> config set <section.key> <value>
hermes -p <profile> config get <section.key>
hermes -p <profile> config check
```

Read back every changed key. Do not rely on the success line from `config set`
alone.

Use `hermes -p <profile> config unset <section.key>` to remove an obsolete
setting. A removed key may resolve to a built-in default; distinguish the
persisted configuration from its resolved value.

## Capability checks

Pair the generic config check with the relevant status commands, for example:

```bash
hermes -p <profile> memory status
hermes -p <profile> curator status
hermes -p <profile> gateway status
```

For platform-scoped capabilities, read the resolved platform toolset and verify
that the intended tool families remain present. Avoid dumping full configuration
when a narrow `config get` is sufficient.

For FamaAgent, verify these boundaries:

- `agent.reasoning_effort` controls reasoning; `model.reasoning_effort` is not
  used by the installed shared reasoning resolver.
- Telegram maintenance requires trusted sender metadata. `allow_from` covers
  DMs; explicitly configure `group_allow_from` for group senders as well.
  `group_allowed_chats` grants a chat, not an individual operator identity.
- `agent.bot_mode_protocol: false` disables the Bot Chat protocol/tool for
  direct agent messaging. `profile.yaml` can keep its visual Bot Mode metadata.
- `no_mcp` suppresses MCP servers, not all other toolsets. Resolve platform
  toolsets and inspect actual tool gates; native toolsets can be recovered.
  Keep CLI/Kanban business capabilities and Telegram maintenance capabilities.
- `security.protected_instruction_files` controls project instruction-file
  approval. Extra patterns apply only when that gate is enabled. The current
  Hermes home is handled separately; this setting is not a filesystem sandbox
  and does not replace the independent native guard on `config.yaml` writes.
- `verify_on_stop` concerns code-edit verification; it does not validate a
  commercial handoff or Markdown-only changes. Test the affected boundary
  using synthetic inputs without external delivery or customer data. If an
  inference is needed, isolate its tools and learning from production state.

Check YAML structure and duplicate keys, context loading/scanning, skill
frontmatter and local reference links. For allowlist or Bot Mode changes,
exercise the real runtime authorization/tool gate with synthetic identities
and session metadata. A generic `config check` alone is insufficient.

## Test runner fallback

Run the repository's declared development runner instead of installing test
dependencies into a long-running service environment:

```bash
uv run --extra dev pytest -q <targeted-tests>
```

A missing command in the service environment is a setup-state issue, not
 evidence that the implementation is unavailable. The supported project runner
must produce the evidence used in the final report.

## Gateway lifecycle

A gateway restart from inside the gateway process is intentionally refused. Use
an external operator shell for lifecycle changes; never evade the guard with an
alternate command. If no external shell is available, leave the persisted
configuration in place, report that reload is pending, and verify the service
has not been stopped.
