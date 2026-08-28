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

## Compaction-summary provenance

To assess whether a marker column reliably identifies compaction summaries,
trace both ends:

- every compressor carrier shape that sets the in-memory marker (standalone,
  merged carrier, and micro-compaction); and
- every persistence path that converts the marker into the integer column.

State the boundary honestly: current generated-and-persisted summaries can be
reliably marked while pre-migration rows with a new column defaulting to zero are
not retroactively classified unless a semantic backfill exists. A database
column enforced only by application code is provenance metadata, not a SQLite
authenticity constraint.

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
3. installed-source tracing with current line ranges.

A server can be CLI-only through `platform_toolsets` only when other platforms
use `no_mcp` or an explicit MCP allowlist that excludes it. Do not generalize a
fresh CLI manifest to schemas already cached in a live conversation.

## Closeout

Re-run Git status for both `/root/.hermes` and the installed Hermes tree. A
read-only audit creates no commit. If the workspace was already dirty, list the
paths without attributing them to the audit unless a pre-audit baseline proves
provenance.
