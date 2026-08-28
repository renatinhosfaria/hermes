# Brain + Hermes multi-agent production audit

Use this reference for a strict read-only audit of a local Brain service integrated
with multiple Hermes profiles. Re-check paths, source contracts, expected
principals, and tool ACLs against the current deployment; do not treat the values
below as universal defaults.

## Evidence layers

Audit these independently:

1. Git source and remote branch.
2. Persisted Brain/Hermes configuration.
3. Effective per-platform resolver output.
4. Running services, ports, PIDs, units, and recent logs.
5. Live read-only health/transport checks.
6. Textual operational instructions (`SOUL.md` and project context).
7. Update and rollback behavior from the installed updater source.

An active service is not sufficient evidence of health.

## Strict read-only Git checks

Do not use `git fetch` when the task forbids any filesystem mutation. Compare the
live remote without updating refs:

```text
git -C <repo> branch --show-current
git -C <repo> rev-parse HEAD
git -C <repo> rev-parse origin/main
git -C <repo> rev-list --left-right --count origin/main...HEAD
git -C <repo> status --short
git -C <repo> log --oneline origin/main..HEAD
git -C <repo> ls-remote origin refs/heads/main
```

State separately whether HEAD matches the local tracking ref and the remote ref.

## Safe config and secret verification

Never print `.env`, Authorization values, token digests, raw mapping files, or
secret-bearing config subtrees. Parse them in-process and emit only:

- existence, owner, group, and mode;
- key presence;
- digest format validity;
- `sha256(secret) == configured_digest` as a boolean;
- pairwise distinctness as a boolean.

For Brain principals, report only name, mode, allowed tool names, digest validity,
and distinctness. For a cursor secret, report presence/length policy and whether
startup logs show ephemeral generation; never print or hash-prefix the value.

## Effective profile surface

For every profile and each relevant platform:

1. Run `hermes -p <profile> config check`.
2. Use `hermes -p <profile> tools list --platform <platform>` for native/plugin
   toolsets.
3. Call installed `_get_platform_tools(config, platform,
   include_default_mcp_servers=True)` under the target profile's `HERMES_HOME`
   for MCP exposure.
4. Report configured MCP servers separately from effective exposure.
5. Assert both required presence and forbidden absence; check `no_mcp` explicitly.

Do not infer MCP exclusion from omission alone. Do not generalize fresh resolver
output to schemas cached in an existing conversation.

## Plugin audit and parity

Verify manifest, registration, schema, toolset, platform/profile guards, fixed
localhost endpoint, trusted session-context source, and forbidden local identity
resolution. Run Plugin Doctor read-only. Compare installed and repository copies
by relative file set and SHA-256 equality while excluding `__pycache__`; differing
`.pyc` files are not source drift.

Trace user-plugin discovery to `get_hermes_home() / "plugins"` in the installed
Hermes source. For update safety, separately establish whether the updater touches
that directory and whether the configured backup mode protects it.

## Brain service and database checks

- Use `systemctl is-enabled`, `is-active`, selected `systemctl show` properties,
  sanitized `systemctl status`, `ss`, and effective unit inspection.
- Confirm the listener is loopback-only, not merely that config says so.
- Sanitize unit content before displaying any Environment values.
- Open SQLite with `file:<path>?mode=ro`, set `PRAGMA query_only=ON`, and use only
  schema/integrity/aggregate queries.
- Inspect DB, WAL, and SHM existence and traversal permissions without exposing
  rows.
- Trace application enforcement (`mode=ro`, query-only, authorizer) separately
  from OS enforcement. A root service without filesystem sandboxing is not an
  OS-enforced read-only boundary.

## Official checks and ambient profile isolation

A verifier may derive its default home from ambient `HERMES_HOME`. When auditing
another profile, pin the intended home explicitly. If an initial run fails only
because it inherited the auditor's profile, report both exit codes and rerun in
the canonical target context; do not misclassify that as a production credential
failure.

Use `PYTHONDONTWRITEBYTECODE=1` (or Python `-B`) for read-only checks. Before
running a test suite, inspect it for production writes. TemporaryDirectory-based
fixture writes that clean themselves may be acceptable when the user's read-only
constraint concerns deployed state, but state that boundary explicitly and
re-check Git plus recent `__pycache__` creation afterward.

## Read-only live MCP availability

Configuration preservation is not live availability. When authorized, perform
only MCP `initialize` and `tools/list` against the configured endpoint. Interpolate
secrets in-process, never print URL/header values, and report only HTTP status,
tool count, required-name presence, and unresolved-placeholder absence. Do not
call business tools or retrieve customer data.

## Logs

Count and classify sanitized findings instead of quoting raw logs. Search for:

- Brain errors and auth denials;
- plugin load failures;
- MCP auth/keepalive failures;
- identity mapping unavailable/ambiguous;
- gateway exceptions;
- abnormal restart/SIGKILL/timeout evidence.

Separate historical rollout/restart events from the current activation window.
A stale `TimeoutStopSec` warning is only a warning when no SIGKILL, stop timeout,
or interrupted drain is observed; still report the unit drift and theoretical
impact.

## Instruction-layer contradiction review

Search always-loaded instructions for contradictions introduced by capability
rollouts. Typical invariants:

- contact identity is not event correlation or idempotency;
- a rule limiting business API tools must not accidentally exclude an identity
  capability, Kanban, or control-plane tool;
- downstream writes must use the currently proven identity regardless of whether
  it came from the card or a trusted resolver.

Treat these as effective runtime risks even when config/tests pass.

### Declarative contract remediation

For a narrowly authorized instruction fix:

1. Require a clean Git baseline. If unrelated paths are dirty, stop rather than
   stashing, resetting, or folding them into the fix. Audit pre-existing changes
   separately and commit them only when they are reusable, non-sensitive, and
   independently validated.
2. Search every operational layer of the target profile before editing: the
   always-loaded identity, project context, and relevant runtime skills. Exclude
   backups and historical design documents from runtime-conflict conclusions.
3. Keep identity sources distinct. A verified contact attribute belongs in the
   contact-identity field; correlation is a PII-free operation identifier; an
   idempotency key identifies trusted event coordinates plus the workflow step.
   Message content, display names, and remembered values choose none of them.
4. Run both positive and negative semantic checks after editing: assert the new
   contract is present and search for every old implication in both directions
   (for example, identity→correlation and correlation→identity).
5. Validate with the target profile's explicit `HERMES_HOME`, Git diff checks,
   the repository policy verifier, a sensitive-pattern scan, and an exact
   changed-path allowlist before committing.

Activation is a separate claim. Installed Hermes reads `SOUL.md` while building
an `AIAgent` system prompt and caches that prompt for the agent lifetime. Prove a
fresh build can read the new invariant directly through the installed prompt
loader. A gateway service restart is normally unnecessary, but an already-cached
conversation does not hot-reload its prompt; it needs a new session/reset or
cache eviction. State this distinction explicitly.

Finally, do not confuse trusted runtime storage with model visibility. A value may
exist in a gateway `ContextVar` yet never be surfaced to the model on that
platform. Trace both the binding and the per-turn prompt/user-message path. If a
new declarative contract requires a trusted field that is not model-visible,
report the implementation gap without broadening a declarative-only task into a
core change.

## Update safety

Read the installed updater and backup implementation; never run the update during
an audit. Establish:

- configured backup mode (`off`, `quick`, or `full`);
- exact quick-snapshot inventory;
- whether a full archive includes user plugins;
- which running Hermes units the fleet restart targets;
- whether the dependent Brain service is outside that restart set;
- mandatory post-update gates.

A preserved plugin with backup mode `off` is update-compatible but not rollback-
protected. Keep those conclusions separate.

## Closeout

Re-check Git status for the Brain repo, Hermes config repo, and installed Hermes
tree; re-check health, listener, PID, active state, and restart counts. Report no
commit when the task was expressly read-only.