# Atendimento incident channel implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement the approved design task by task. Policy scenarios receive a separate read-only review under writing-skills.

**Goal:** Keep WhatsApp silent when a valid response is unavailable and reliably alert Renato in the existing Dev Telegram channel.

**Architecture:** Extend the already installed five-minute systemd fleet watcher. Read Hermes databases only; detect blocked/stalled tasks and unanswered external messages, persist alert deduplication outside /run, and use the existing independent Telegram delivery and bounded Dev diagnosis. No new cron, automatic repair, or automatic replay.

**Tech Stack:** Python standard library, existing PyYAML, SQLite read-only, existing systemd timer and Telegram Bot API.

**Spec:** User-approved design in this conversation, refined by discovery of the existing fleet watcher.

## Global constraints
- No WhatsApp messages or changes to CRM, task status, or client history.
- Telegram destination comes only from Dev configuration. Secrets never enter command arguments or output.
- Distinguish expected null payload from Porteiro/Cadastro success, pending retries, and human handover.
- Technical task/session references only in incident alerts; no customer names, phones or message bodies.
- Do not restart the Hermes gateway until isolated tests and local production read-only checks pass.
- A cleared signal is not proof that the lead was answered; resume requires operator verification.

## Task 1: Read-only incident detection
**Files:** Create `ops/observability/attendance_incidents.py` and `ops/observability/tests/test_attendance_incidents.py`.
**Interface:** `detect(root: Path, timestamp: float) -> list[dict]`, findings with stable `sig`, `area`, `message`, `severity`, `immediate`.
- [x] Tests with temporary SQLite fixtures: blocked capability, triage, runtime exceeded, pending retry suppression, normal classifier success, missing Reno response, internal notification exclusion, human handover, pending external message, database unavailable, no raw data in findings.
- [x] Run tests before implementation and verify missing detection fails.
- [x] Implement queries against installed schema; never write operational databases.
- [x] Verify tests and read-only live detection.

## Task 2: Reliable independent alerts
**Files:** Modify `ops/observability/fleet_watch.py`; create `ops/observability/tests/test_fleet_alerts.py` and systemd drop-in template.
**Interface:** Add attendance probe to fleet watch; `run_alerting` reports delivery success; bounded Telegram payloads and durable deduplication.
- [x] Test initial immediate alert, duplicate suppression across runs, retry after delivery failure, old three-scan fleet threshold, bounded batches and no recovery claims when detection is unavailable.
- [x] Integrate detection, persistent state and safe Telegram transport from Dev config.
- [x] Confirm alert failure is observable to systemd; monitor remains independent of CEO/Kanban runtime.

## Task 3: Policy and operation
**Files:** Modify CEO `SOUL.md`, `skills/business-operations/fama-ceo-runtime/SKILL.md`, Dev `fama-fleet-observer/SKILL.md`, and `ops/hermes-team/RUNBOOK.md`.
- [x] Replace contradictory never-silent instructions with silent external handling and authoritative task/comment incident evidence.
- [x] Explain task marker, independent fallback, investigation-only Dev role, manual resumption and actual timer frequency.
- [x] Re-test five policy scenarios after edits and review code.
- [x] Run unit tests and installed configuration checks; commit only this change and integrate into live checkout.
- [x] Migrate watcher deduplication state to persistent directory, install reviewed drop-in and activate monitor with an explicit Telegram activation check.
- [x] Refresh CEO instruction snapshots through native SessionDB API and gracefully restart CEO when no turn is in flight. Preserve all message history.
- [x] Verify timer, delivery, policy snapshots, and clean scoped diff; report limitations.

Validation before rollout: 24 detector/alert tests plus native instruction-refresh test. Independent review found and resolved run-clock, historical-failure and pending-delivery bugs. Gateway-generated error messages remain outside this prompt-policy change and are explicitly documented.


## Rollout evidence

- Integrated locally as `2493f6a`; no remote publication.
- 25 incident/alert/native-refresh tests and 18 existing CTWA tests passed.
- Existing systemd monitor retained its five-minute cadence; state migrated from
  `/run/hermes-fleet-watch` to `/var/lib/hermes-fleet-watch` without deleting the old state.
- Telegram Bot API confirmed the explicit channel test and delivery of eight
  existing attendance findings; `pending.json` was empty after the scan.
- Monitor completed successfully at 2026-09-08 15:46:23 America/Sao_Paulo.
- CEO restarted gracefully through the native CLI. Temporary ExecStartPre used
  the native SessionDB API to clear 113 obsolete gateway instruction snapshots.
  Subsequent read-only check found zero old-policy snapshots in gateway sources.
  The temporary drop-in was removed after successful startup.
- Automatic Dev diagnosis was requested for the grouped attendance findings,
  subject to the existing hourly budget. No automatic repair or task replay.
- Limitation: prompt silence does not suppress diagnostics generated directly
  by the installed Hermes gateway; those are explicitly outside this change.
