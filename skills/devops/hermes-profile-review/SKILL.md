---
name: hermes-profile-review
description: "Review Hermes profiles safely."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, profiles, configuration, security, diagnostics, review]
    category: devops
---

# Hermes Profile Review

Review an individual Hermes profile without changing it. Produce an evidence-based assessment of configuration validity, authentication, enabled capabilities, runtime state, file protection, and actionable risks.

## When to use

Use this skill when someone asks to review, audit, validate, diagnose, or assess a Hermes profile or isolated agent instance. It is for read-only review. Configuration changes require a separate, explicitly authorized setup or remediation workflow.

## Operating principles

1. **Resolve the profile first.** Confirm the profile name and its actual home directory with `hermes profile list` and `hermes profile show <name>`. Do not infer a profile path from a display name.
2. **Keep scope profile-local.** Run profile-sensitive commands with `HERMES_HOME=<profile_path>` when supported. Some commands may still report global/runtime state; label that output as global instead of attributing it to the profile.
3. **Never expose secrets.** Do not print `.env`, `auth.json`, tokens, API keys, phone numbers, or raw credentials. Inspect only existence, permission bits, key names, and provider status.
4. **Prefer native diagnostics.** Use `hermes config check`, `hermes config`, `hermes doctor`, `hermes tools list`, and `hermes security audit` rather than parsing implementation internals first.
5. **Separate evidence from judgment.** Report facts observed from commands, inferences about risk or suitability, and unknowns that require an owner decision.
6. **Do not silently remediate.** A review must not run `hermes setup`, `doctor --fix`, dependency upgrades, profile edits, gateway changes, or auth changes unless the request explicitly includes remediation.

## Review procedure

### 1. Establish identity and scope

Run:

```bash
hermes profile list
hermes profile show <profile>
```

Record the canonical profile path, model/provider, gateway state, presence of `.env`, `SOUL.md`, and auth metadata. Treat profile display names and aliases as labels, not as paths.

### 2. Inspect configuration safely

Read the profile's `config.yaml` through a file reader. Check model/provider, base URL, context length, reasoning, terminal backend/cwd/timeout, memory behavior, checkpoints, approvals, platform configuration, and toolset bundles. Never include secret values in the report.

Then run:

```bash
HERMES_HOME=<profile_path> hermes config check
HERMES_HOME=<profile_path> hermes config
```

If the command output unexpectedly points at another Hermes home, mark the result as global or ambiguous and do not use it as profile evidence.

### 3. Verify runtime and capability state

Run, as supported:

```bash
HERMES_HOME=<profile_path> hermes doctor
HERMES_HOME=<profile_path> hermes tools list
```

Use `hermes tools list` rather than assuming a YAML `toolsets` entry fully describes the effective tool surface. Note dangerous or high-impact capabilities separately: terminal, code execution, browser, computer use, cron, delegation, messaging, and external integrations.

Check whether the gateway is intentionally stopped or simply unhealthy. A stopped gateway is not a defect for an on-demand internal profile unless continuous messaging was required.

### 4. Check security and file protection

Run:

```bash
HERMES_HOME=<profile_path> hermes security audit
stat -c '%A %a %U:%G %n' <profile_path>/config.yaml <profile_path>/.env <profile_path>/auth.json <profile_path>/SOUL.md
```

On non-Linux systems, use the native permission inspection equivalent. Sensitive files should be owner-only where the platform supports it. Report missing files, overly broad permissions, or failed audits distinctly.

### 5. Classify findings

Use three explicit labels:

- **Fato:** directly returned by a command or file inspection.
- **Inferência:** a reasoned suitability or risk judgment based on the facts.
- **Desconhecido:** information not established by the available evidence.

Assess at minimum:

- configuration validity and deprecated keys;
- authentication readiness and whether it relies on OAuth or API keys;
- profile-local versus global runtime state;
- tool surface versus least privilege;
- write approvals for skills, memory, and destructive actions;
- terminal backend and working directory isolation;
- gateway/channel exposure;
- file permissions and supply-chain audit results;
- model context/reasoning settings versus expected latency and cost.

### 6. Report without overclaiming

Start with a short verdict such as *aprovado para uso interno sob demanda*, *aprovado com ressalvas*, or *não aprovado*. Follow with verified facts, strengths, attention points, and the smallest recommended next decisions. State clearly when no configuration was changed.

Do not treat optional missing credentials, disabled channels, a stopped gateway, or uninstalled optional dependencies as defects without a requirement that calls for them.

## Reusable reference

See `references/profile-review-checklist.md` for the compact command matrix and reporting template.

## Pitfalls

- **Wrong home:** running `hermes status` or another command without `HERMES_HOME` can describe the active/default profile instead of the target profile.
- **Config-only tool review:** a short `toolsets` list may be a bundle; verify effective tools with `hermes tools list`.
- **Secret leakage:** `hermes doctor` and `status` can mention credential paths and provider state; summarize them without copying tokens or raw environment files.
- **Global advisories misattributed:** workspace dependency warnings may be global/shared and not a vulnerability in the target profile. Run the profile security audit and label scope.
- **Review becoming remediation:** do not use `doctor --fix` or edit `config.yaml` during a read-only review.
- **Certainty inflation:** a valid config means syntactically and diagnostically healthy, not automatically least-privilege or fit for every workload.

## Acceptance checklist

- [ ] Canonical profile path verified.
- [ ] Profile config inspected without exposing secrets.
- [ ] Profile-scoped diagnostics run, or scope limitations recorded.
- [ ] Effective tools checked separately from config bundles.
- [ ] Security audit and sensitive-file permissions checked.
- [ ] Facts, inferences, and unknowns separated.
- [ ] No changes made during review unless explicitly authorized.
- [ ] Verdict is concise and actionable.
