# Read-only SQLite and MCP runtime audits

Use this reference when an audit must prove live database shape, filesystem
access, or per-platform MCP exposure without mutating Hermes state.

## SQLite: prove schema without opening a writer

Open live databases with a URI and `mode=ro`:

```python
import sqlite3
conn = sqlite3.connect("file:/path/to/state.db?mode=ro", uri=True)
```

Then use only read statements such as:

```sql
PRAGMA table_info(messages);
SELECT sql FROM sqlite_master WHERE type='table' AND name='messages';
SELECT COUNT(*) FROM some_table;
SELECT MAX(id) FROM messages;
```

`PRAGMA table_info` is the primary evidence for column existence, nullability,
primary-key position, and declared default. Quote its raw rows before interpreting
them. Use `sqlite_master.sql` only as complementary evidence for the effective
CREATE TABLE text.

For a privacy-preserving inventory of populated columns, enumerate the names
from `PRAGMA table_info` and test each with `EXISTS`; report only the column names,
never row values or participant identifiers. Distinguish `NULL` from an empty
string explicitly.

## Filesystem access: inspect the whole traversal path

A database file and its `-wal`/`-shm` sidecars may be world-readable while an
unprivileged process still cannot open them. Capture permissions for every parent
directory and the database family. A parent such as `/root` or `/root/.hermes`
with mode `0700` blocks traversal before SQLite reaches a `0644` database.

When the claim concerns a running gateway:

1. Prove the gateway PID is live, not merely that a stale PID file exists.
2. Capture `db`, `db-wal`, and `db-shm` in the same command batch as the
   unprivileged read probe and privileged aggregate query.
3. Run the exact unprivileged probe requested and quote the exception type and
   message. A caught exception can coexist with process exit code 0; report both
   semantics correctly.
4. Do not create a test user, chmod paths, restart the gateway, checkpoint WAL,
   or open the database without `mode=ro` just to make the probe pass.

The absence of a `-wal` or `-shm` file is a snapshot fact, not proof that the
database never uses WAL.

## Compaction-summary provenance and display deduplication

To assess whether a marker column reliably identifies compaction summaries,
trace both ends:

- every compressor carrier shape that sets the in-memory marker (standalone,
  merged carrier, and micro-compaction); and
- every persistence path that converts the marker into the integer column.

State the boundary honestly: current generated-and-persisted summaries can be
reliably marked while pre-migration rows with a new column defaulting to zero are
not retroactively classified unless a semantic backfill exists. A database
column enforced only by application code is provenance metadata, not a SQLite
authenticity constraint. A marked row can also be a merged carrier containing
both preserved human content and a synthetic summary; the marker means
"contains a summary", not necessarily "the whole row is synthetic".

For `SessionDB.get_messages(include_compacted=True)`, reproduce the installed
algorithm rather than deduping on `content` alone:

1. select rows with `active = 1 OR compacted = 1` for the session;
2. form the logical key `(role, dedupe_content, timestamp, tool_call_id,
   tool_calls, tool_name)`;
3. for a composite `user` summary carrier, project its human-authored live view
   and use that encoded content as `dedupe_content`; otherwise use stored
   `content`;
4. within each key, prefer maximum `(active, id)` — any live row beats every
   archived copy, then the newest id wins within equal active state;
5. sort winners by id, then apply offset/limit. For latest paging, select from
   newest first but return the selected page chronologically.

A SQL `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY active DESC, id DESC)` is
exact only after `dedupe_content` has been computed. Pure `content` partitioning
misses composite-carrier versus original-human copies. Exact external parity
requires reimplementing the user-carrier projection (or exposing it as a SQL
UDF); do not substitute a textual prefix check. `compacted=1` marks archive
provenance, not synthetic-summary identity; `display_kind='hidden'` is auxiliary
and non-universal. No separate compaction-generation id is persisted.

## MCP platform semantics

Audit `_get_platform_tools` in the installed `hermes_cli/tools_config.py` and its
call sites. `include_default_mcp_servers=True` has non-obvious semantics:

- one or more explicit MCP server names form an allowlist;
- `no_mcp` disables all MCP servers for that platform;
- otherwise every globally enabled MCP server is added, even when the platform
  has an explicit list containing only native toolsets such as `clarify`.

Therefore, omission of a server name is not exclusion. Prove behavior at three
layers:

1. `hermes -p <profile> config get platform_toolsets`;
2. `hermes -p <profile> tools list --platform <platform>`;
3. direct `_get_platform_tools(config, platform)` resolution and installed-source
   tracing with current line ranges.

Do not treat the MCP section of `hermes tools list --platform` as standalone
proof of platform exposure. The command resolves native toolsets with
`include_default_mcp_servers=False`, while `_print_tools_list` enumerates every
configured MCP server and reports its per-server include/exclude filters without
checking membership in the platform's resolved set. Use the default-true
resolver path used by the gateway to prove effective exposure.

A server can be CLI-only through `platform_toolsets` when other platforms use
`no_mcp` or an explicit MCP allowlist that excludes it. This is enforced before
the server: the omitted toolset does not contribute schemas, model-emitted names
are checked against `agent.valid_tool_names`, and the tool-search bridge checks
its scoped catalog. Server-side auth/policy remains defense in depth, not the
only containment. Do not generalize a fresh resolver result to schemas already
cached in a live conversation.

### Multi-profile topology verifiers

When turning an audit into a deterministic team verifier:

1. Enter each profile's Hermes-home scope before calling `_get_platform_tools`;
   ambient `HERMES_HOME` can otherwise resolve the wrong profile.
2. Assert the required `platform_toolsets.<platform>` entries individually unless
   the contract explicitly forbids additional platform entries. Comparing the
   whole mapping can reject legitimate unrelated surfaces such as WhatsApp or
   Discord on the default profile.
3. Call `_get_platform_tools(config, platform,
   include_default_mcp_servers=True)` for every profile/platform pair. Intersect
   the resolved set with the known configured MCP-server universe, then assert
   and print both `present` and `absent` sets. This catches accidental exposure
   and makes a passing report auditable.
4. Keep configured-server assertions separate from exposure assertions: a server
   can be configured globally yet intentionally absent from one platform.
5. After changing the verifier, run it normally and then run a focused temporary
   checker from an OS-generated path such as `/tmp/hermes-verify-*.py`. The
   checker should assert exit code zero, every expected MCP line, no `FAIL:` line,
   and the final `PASS`; remove it immediately afterward and label it ad hoc.

## Closeout

Re-run Git status for both `/root/.hermes` and the installed Hermes tree. A
read-only audit creates no commit. If the workspace was already dirty, list the
paths without attributing them to the audit unless a pre-audit baseline proves
provenance.
