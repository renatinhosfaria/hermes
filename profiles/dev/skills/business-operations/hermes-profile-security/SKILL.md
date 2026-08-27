---
name: hermes-profile-security
description: "Secure and verify Hermes gateway profile configuration."
version: 0.1.0
author: Renato Faria, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Hermes, gateway, profiles, Telegram, security, toolsets]
    related_skills: []
---

# Hermes Profile Security Skill

Use this skill when configuring or diagnosing a Hermes profile's messaging
routing, gateway authorization, toolset scope, or restart state. It favors
read-before-write evidence, least privilege, and explicit separation between
persisted configuration and the process currently running. It does not change
credentials, platform sessions, live state databases, or the read-only Hermes
installation.

## When to Use

- Verifying that a gateway loaded a profile configuration after restart.
- Securing Telegram access with DM and group allowlists.
- Confirming a profile's home channel and topic/thread routing.
- Auditing which toolsets and individual tools a gateway session actually has.
- Investigating why a persisted toolset or access setting is not active.

Do not use this skill to call Telegram `getUpdates` while the bot gateway is
long-polling, to print bot tokens or `.env` contents, or to restart a service
unless the user explicitly authorizes that operational action.

## Prerequisites

- The target profile name and its Hermes home are known.
- The installed Hermes source under `/usr/local/lib/hermes-agent` is treated as
  read-only and may be consulted when CLI output conflicts with configuration.
- The profile's `config.yaml` and runtime logs are inspected before mutation.
- Existing Git changes are recorded; only the requested configuration file is
  staged for a configuration commit.

## Quick Reference

Use these through the Hermes tools, with `terminal` for CLI commands and
`read_file`/`search_files` for file inspection:

```text
hermes -p <profile> config get <key>
hermes -p <profile> config set <key> <value>
hermes -p <profile> config unset <key>
hermes -p <profile> config check
hermes -p <profile> tools list --platform telegram
```

Relevant Telegram configuration paths in the current Hermes runtime:

```text
platforms.telegram.home_channel.platform
platforms.telegram.home_channel.chat_id
platforms.telegram.home_channel.name
platforms.telegram.home_channel.thread_id
platforms.telegram.home_channel.user_id
telegram.allow_from
telegram.group_allowed_chats
telegram.require_mention
```

## Procedure

1. **Establish a read-only baseline.** Check the profile's Git status, inspect
   the relevant YAML, and identify the gateway process without exposing
   credentials. Record unrelated changes; never overwrite them.

2. **Validate current runtime state from recent log entries.** Inspect the
   latest matching lines, not an arbitrary historical match. For dispatcher
   state, the expected current message when the profile must not dispatch
   Kanban is `disabled via config kanban.dispatch_in_gateway=false`. An older
   `another gateway already holds the dispatcher lock` line may be historical;
   report it separately rather than treating it as the current state.

   For a home-channel change, compare explicit notification lines immediately
   before and after the relevant restart. A line such as
   `Sent home-channel startup notification to telegram:<CHAT_ID>` records the
   channel actually resolved by that gateway startup; a corresponding failure
   line also records the attempted resolved ID. By contrast,
   `Channel directory built: <N> target(s)` does not identify the home channel
   and must not be used to infer it. If no explicit ID-bearing line exists,
   report that the log does not establish the resolved channel instead of
   substituting the persisted YAML or an expected group ID.

3. **Audit the actual tool surface.** Run
   `hermes -p <profile> tools list --platform <platform>` and map enabled
   toolsets to individual tools. The bare `hermes tools` command may require an
   interactive terminal; the `tools list --platform` form is suitable for a
   non-interactive diagnostic.

   Treat the tool manifest as authoritative. If a requested reduction says
   browser, delegation, code execution, computer control, TTS, or vision should
   be absent but the platform listing still enables those toolsets, report the
   mismatch; do not claim success from the YAML alone.

   For the currently running conversation, the actual function namespace is a
   separate fact: inspect the tools exposed to the session and do not substitute
   `hermes tools list` for a claim about already-loaded function schemas. A
   platform listing can change on disk while an existing session keeps its
   cached prompt/tool manifest until reset or restart.

4. **Resolve the toolset configuration layer before changing it.** In the
   installed runtime, gateway platform sessions resolve
   `platform_toolsets.<platform>`. A top-level `toolsets` list can remain
   persisted while failing to constrain a Telegram gateway. When these disagree,
   inspect `hermes_cli/tools_config.py` and use the documented platform-specific
   configuration path or `hermes tools` workflow. Do not broaden the scope of an
   access-control task silently; report a separate pending toolset correction if
   it was not requested.

5. **Audit Telegram environment overrides without exposing unrelated data.**
   Default to counts for `.env` keys and never dump or quote the file wholesale.
   If the authorized operator explicitly classifies specific identifiers as
   non-secret and requests their values, print only exact allowlisted keys such
   as `TELEGRAM_HOME_CHANNEL` and `TELEGRAM_ALLOWED_USERS`; suppress every other
   line. Classify a home-channel value against the supplied profile-to-group map,
   but do not describe a user ID as a group ID. Inspect the running gateway's
   `/proc/<PID>/environ` only for variable presence/count unless disclosure of
   that exact value is separately authorized. A zero process-environment count
   is evidence about that process environment, not proof that every internal
   `.env` loader path is inactive.

   Treat persisted YAML, `.env` presence, process environment, and post-restart
   log resolution as separate facts. A successful `config set` does not prove
   that a stale environment variable stopped overriding the adapter. If local
   policy forbids editing `.env`, leave it untouched and report the resulting
   activation risk instead of presenting the YAML-only change as complete.

6. **Use the adapter's documented access paths.** For Telegram, persist the
   sender allowlist and group restriction with:

   ```text
   hermes -p <profile> config set telegram.allow_from '<USER_ID>'
   hermes -p <profile> config set telegram.group_allowed_chats '<GROUP_ID>'
   ```

   `telegram.allow_from` must cover DMs as well as group senders. The group
   restriction is defense in depth if the bot is added elsewhere. If a stale
   `TELEGRAM_ALLOWED_USERS` key exists in the YAML root, remove that root key
   with `config unset`; do not edit `.env` directly merely to clean up a
   configuration audit.

7. **Verify persisted state and commit narrowly.** Run `config get` for every
   changed key, run `hermes -p <profile> config check`, inspect `git diff --check`,
   and ensure only the intended `config.yaml` is staged. `config set` may
   reserialize the YAML and remove preexisting comments or formatting; treat
   those as collateral changes, preserve the original non-semantic content, and
   re-run the checks until the diff contains only the requested setting. For a
   multi-profile change, a temporary focused verifier may check YAML parsing,
   resolved values, and forbidden/unrequested keys together; remove it after
   execution and report it as ad-hoc verification, not as a canonical test
   suite. Commit with a descriptive message; never push.

8. **State activation separately from persistence.** Unless the user explicitly
   authorizes a restart, do not restart or reload the gateway. Report that the
   configuration is persisted and that the process will need the owner's restart
   before new settings are assumed active.

## Pitfalls

- **Do not call `getUpdates`.** A manual polling call can compete with the
  gateway's long-polling bot and steal updates.
- **Do not trust the old CEO/home-channel ID.** Confirm the live channel from
  session metadata, sanitized gateway logs, or a safe `getChat` call authorized
  by the user; never infer it from profile defaults alone.
- **A root `TELEGRAM_ALLOWED_USERS` warning is meaningful.** `config set` may
  save an unrecognized custom key and bridge it to `.env`, while the Telegram
  adapter's documented path remains `telegram.allow_from`. Verify both storage
  locations and remove only the stale YAML-root copy when requested.
- **`config check` can still report `TELEGRAM_ALLOWED_USERS` as present after
  the YAML key is removed** because the `.env` entry remains. This is not proof
  that the YAML root key survived.
- **A successful config write is not a live-runtime verification.** Check the
  process, logs, or a post-restart diagnostic; never claim the gateway has
  adopted a value before the owner restarts it.
- **Do not print tokens, invite links, full `.env` files, or full raw Telegram
  updates.** Prefer counts and sanitized IDs. When the operator explicitly
  authorizes named non-secret keys, emit only those exact key/value lines and
  suppress all neighboring content.

## Verification Checklist

- [ ] Latest ID-bearing home-channel log lines were compared across the relevant
      restart; generic directory-build lines were not treated as channel proof.
- [ ] Recent dispatcher log shows the intended current mode.
- [ ] Tool presence/absence is reported from the platform tool listing, not only
      from persisted YAML.
- [ ] `telegram.allow_from` and `telegram.group_allowed_chats` return the
      intended values with `config get`.
- [ ] Stale YAML-root `TELEGRAM_ALLOWED_USERS` is absent when applicable.
- [ ] `.env` inspection exposed no unrequested line or secret; any printed value
      belonged to an exact operator-authorized non-secret key.
- [ ] Persisted YAML, environment presence, running-process state, and
      post-restart resolution are reported as separate evidence layers.
- [ ] `hermes -p <profile> config check` passes.
- [ ] Only the requested files are staged and committed.
- [ ] Restart status is stated explicitly; no unrequested restart occurred.

Session-specific runtime evidence and source-code notes are kept in
`references/telegram-gateway-diagnostics.md`.
