---
name: hermes-runtime-verification
description: "Use when auditing Hermes runtime behavior from source."
license: MIT
version: 1.0.0
author: Fama Negócios Imobiliários
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, runtime, profiles, toolsets, skills, prompt, gateway, verification]
    related_skills: [hermes-profile-security, hermes-agent]
---

# Hermes Runtime Verification

Use this class-level skill to investigate how the installed Hermes Agent
actually behaves for a profile, platform, gateway, toolset, MCP surface, or
system-prompt assembly. Prefer evidence from the live installed source at
`/usr/local/lib/hermes-agent` and from real CLI output over assumptions from
configuration files or generic documentation.

This is an inspection skill. It is suitable for read-only audits and for
verifying a separately authorized configuration change; it does not authorize
writes to the Hermes installation, credentials, live state databases, platform
sessions, or production systems.

## Core principles

- Separate three layers: persisted profile configuration, the tool schemas
  resolved for a new session, and the prompt/runtime state of an already-running
  session. They can legitimately differ until restart or reset.
- Treat `/usr/local/lib/hermes-agent` as read-only source code. Never patch,
  install into, or otherwise modify it.
- Never print credentials, `.env` contents, bearer tokens, cookies, auth files,
  or raw platform updates. For a secret-bearing `config get`, report only that
  the field is masked or a placeholder and omit the value, including fragments.
- Report facts, inferences, and unknowns separately. Include command exit codes
  and real output relevant to the acceptance criterion.
- Preserve exact identifiers and config keys. Do not normalize a value merely
  because it looks unusual.

## When to use

- Auditing a profile's gateway dispatch mode and recent runtime logs.
- Confirming the effective toolset surface for a specific platform.
- Checking whether an MCP server appears in the resolved tool listing without
  exposing its authorization value.
- Explaining whether a profile skill directory is scanned, indexed, injected,
  or reachable through explicit invocation.
- Resolving apparent conflicts between `config.yaml`, CLI listings, source code,
  and an already-running gateway.

## Read-only verification procedure

1. **Define the claim and target.** Record the profile, platform, log path, and
   exact acceptance condition. Do not infer a gateway log path from the default
   profile; locate the target profile's effective log first.

2. **Capture the persisted/runtime baseline.** Run only the requested read-only
   commands, normally including:

   ```text
   hermes -p <profile> config check
   hermes -p <profile> tools list --platform <platform>
   hermes -p <profile> config get <key>
   git -C /root/.hermes status --porcelain
   git -C /root/.hermes log --oneline -8
   ```

   For gateway state, inspect the profile's runtime log and select the latest
   matching entries, not an arbitrary historical match. The platform listing is
   evidence about the resolved surface for that invocation; it is not by itself
   proof about schemas already cached in another live conversation.

3. **Sanitize before reporting.** Preserve safe structural output such as a
   server name, URL, and header key, but replace a secret value with
   `[valor omitido]`. If a command emits an unsafe value, do not quote it in the
   report; state that the command returned a masked/secret-bearing field and
   provide only the safe structure.

4. **Trace behavior in source.** Start at the CLI or gateway entry point and
   follow the actual data path. For tool access, inspect `model_tools.py` and
   the tool registration's `toolset` field. For prompt assembly, inspect
   `agent/system_prompt.py`, then the helper it calls in `agent/prompt_builder.py`
   or `agent/skill_commands.py`. Cite absolute file paths and line ranges from
   the installed tree.

5. **Distinguish automatic from explicit skill loading.** Do not answer a
   question about the `skills` toolset using only the existence of files under
   `skills/`. Establish separately whether:

   - the normal system-prompt skill index is built;
   - `skills_list`, `skill_view`, or `skill_manage` schemas are available;
   - a launch-time preload such as `-s` follows a separate direct-loading path;
   - slash-skill invocation is handled by a separate gateway/CLI path; and
   - `skills.disabled` or platform-specific disablement blocks that explicit
     load.

6. **Close the audit.** Re-run the relevant Git status check and confirm the
   installed tree remains unchanged. A read-only audit must not create a commit,
   mutate configuration, restart a gateway, alter credentials, or touch live
   state. If the user explicitly requested no commit, report that no commit was
   created even if the inspected repository is clean.

## Runtime semantics: toolsets and skills

The installed runtime uses `agent.valid_tool_names` as the bridge between
configured toolsets and prompt behavior. The normal skill index is conditional
on the presence of skill tools in that set. Therefore, a profile that enables
only unrelated toolsets does not automatically inject the contents or index of
its local `skills/` directory into the normal system prompt.

This does not mean the files are universally unreachable. Explicit preloading
(`-s`) and slash invocation have dedicated code paths that may load a skill
payload directly. Check those paths and the disabled-skill configuration before
making an absolute statement that a skill is inaccessible.

The installed source notes and line-level evidence for this distinction are in
`references/skill-injection-and-toolset-gating.md`.

## Remediation pattern: critical conduct behind a disabled skill surface

When source tracing and `tools list --platform` prove that the target platform
omits the `skills` toolset, do not leave runtime-critical conduct only in a
skill that the normal prompt cannot index or load.

1. Move the complete mandatory conduct into the profile's always-loaded
   instruction layer (`SOUL.md` for identity, behavior, and permanent limits;
   project context for operational environment rules).
2. Replace any instruction that tells the agent to load the unavailable skill
   with an explicit statement that the always-loaded file contains the complete
   conduct and that the skill is not the runtime source of truth.
3. Preserve the skill as documentation unless the task separately authorizes
   changing it; do not duplicate contradictory requirements across layers.
4. Verify both text-level acceptance checks and a short, behavior-specific
   inference in a fresh invocation of the target profile. A successful config
   check alone does not prove that the migrated conduct reached the prompt.
5. Respect explicit operational constraints such as no restart, no push, and a
   commit limited to the authorized file.

## Pitfalls

- **Config-only conclusion:** `toolsets:` or `platform_toolsets:` in YAML is
  not enough; use `tools list --platform` and, when necessary, source tracing.
- **Historical log match:** older dispatcher-lock messages can coexist with a
  newer `disabled via config ...` entry. Always report the latest matches.
- **Secret leakage through “real output”:** real output does not require
  reproducing a token. Report its safe shape and explicitly state that the
  value was omitted.
- **Overstating “inaccessible”:** disabled automatic indexing is not identical
  to disabling every explicit preload or slash-command path.
- **Profile leakage:** resolve the agent's own profile home before interpreting
  a skill directory. Do not assume ambient `HERMES_HOME` is correct on gateway
  threads.
- **Live-session confusion:** a new CLI listing does not retroactively change a
  cached system prompt/tool manifest. State whether the evidence concerns a new
  invocation or an existing process.

## Verification checklist

- [ ] Target profile, platform, and effective log path are explicit.
- [ ] `config check` completed and its exit code is recorded.
- [ ] Tool presence/absence came from `tools list --platform`.
- [ ] MCP presence was confirmed without exposing authorization values.
- [ ] Latest relevant log entries were selected.
- [ ] Source file and line ranges support each non-obvious conclusion.
- [ ] Automatic prompt injection and explicit skill loading were distinguished.
- [ ] Both Hermes repository and installed-tree integrity were checked.
- [ ] No files, credentials, live state, platform session, restart, or commit was
      touched during a read-only audit.
