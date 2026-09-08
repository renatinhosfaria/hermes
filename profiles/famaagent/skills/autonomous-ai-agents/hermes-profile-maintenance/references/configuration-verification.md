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
