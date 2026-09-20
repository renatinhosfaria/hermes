---
name: hermes-learning-lifecycle
description: "Use after completed work, corrections or verified reusable procedures to review and persist durable learning in this profile."
version: 1.1.0
author: Fama Negócios Imobiliários
license: MIT
metadata:
  hermes:
    tags: [hermes, learning, memory, skills, lifecycle, persistence, review]
---

# Hermes learning lifecycle

## Purpose

Capture durable user facts and reusable operating procedures without confusing
memory, skills, runtime state, or a successful configuration write. This is a
class-level workflow for learning reviews and lifecycle validation.

## Standing rules

- Save stable identity, preferences, expectations, and durable environment facts
  as memory; save repeatable procedures, decision points, commands, pitfalls, and
  verification criteria as skills.
- Do not save transient task state, raw conversations, third-party PII,
  secrets, unsupported hypotheses, or a procedure that has not worked.
- Prefer strengthening an existing class-level skill over appending a duplicate
  rule; keep always-on behavior and stable user presentation preferences in
  SKILL.md, put only occasional depth in a small topical reference, and never
  create a per-session skill or reference.
- Treat configuration and nudge activation as scheduling evidence only. Prove
  persistence by observing the write and recovering it from an independent
  process in the same profile.
- Follow the user's preferred presentation: procedure first, concrete decision
  points, terminal decision first in structured handoffs, concise evidence on
  following lines, and no artificial learning entry merely to make a review
  non-empty.

## Procedure

1. Review completed work, corrections and verified reusable procedures. On
   short CLI/Kanban workers, do this before the final response and before closing
   the card; background review complements it. SOUL.md supplies the standing
   authorization, so no separate save request or maintenance card is required.
   If no durable lesson exists, finish without manufacturing a memory or skill.
   Extract only facts that remain
   useful beyond the current task and distinguish user facts from procedures.
2. Call `skills_list` to inspect the library. For every candidate target, call
   `skill_view` during the current review before patching its SKILL.md; load an
   exact supporting file before overwriting or removing it.
3. Select the earliest valid destination: patch an editable loaded skill, then
   inspect `skills_list` for an editable existing class-level umbrella, then
   extend a topical reference, and create a new class-level umbrella only when
   no suitable destination exists. If the first target is protected (including
   a refusal that identifies it as not curator-managed or user-owned), do not
   retry it: continue the search before declaring that nothing can be saved.
   Do not edit bundled, hub-installed, externally owned, pinned, or user-owned
   skills when the runtime marks them protected.
4. Patch the sentence that is wrong or incomplete instead of adding an
   incident-style correction below it. Consolidate repeated lessons into one
   imperative rule with a short reason. Name new references by topic, never by
   date, incident, ticket, or error string.
5. Use `memory` for the user fact and `skill_manage` for the procedure. Batch
   related writes atomically where the tools support it. Treat an explicit
   active-learning request or a standing expectation that most reviews yield a
   skill update as a required review gate: save the preference to the user
   profile, inspect at least one relevant loaded class-level skill, search its
   SKILL.md and references for an existing rule, and make one targeted,
   read-before-write patch when the request or completed work supplies a
   verified reusable generalization. Prefer strengthening that loaded skill in
   place; do not treat an already-similar rule as a reason for a no-op when the
   new instruction adds an actionable decision point. Do not manufacture a
   lesson or create a session-specific duplicate; if no safe generalization
   exists or the target is protected, report that boundary. For query-backed
   verification, record source success and completeness separately from
   correlation counts in the handoff evidence, and count a zero-match outcome
   as valid only when both are positive (for example, HTTP status plus an
   explicit truncation/completeness signal); otherwise treat the result as
   unavailable or incomplete rather than as a negative.
6. After a skill write, inspect the tool result and reload the resulting skill
   with `skill_view`. For lifecycle claims, separately verify the persisted
   record in an independent process; never infer persistence from configuration
   alone.

## Lifecycle-specific verification

- Interpret `memory.nudge_interval` as a count of user turns and
  `skills.creation_nudge_interval` as a count of tool iterations; never treat
  the similarly named counters as interchangeable.
- Expect the native review fork only after an uninterrupted final response and
  only when the required learning tools are exposed.
- For one-shot CLI runs, let the official `on_session_finalize` lifecycle hook
  await background review before cleanup, with the configured upper bound of
  300 seconds; gateway channels remain asynchronous and must not be reported as
  synchronously persisted merely because the run ended.
- Validate both creation and later independent recovery of a memory and a skill,
  while also checking profile and channel isolation and the wait bound when
  those behaviors are in scope.

## Reporting

State what was saved, where it was saved, and what was verified. If a candidate
skill is protected or a persistence path is not proven, report that boundary
instead of claiming success. Mention overlapping skills when present so a
background curator can consolidate them.

See `references/persistence-verification.md` for the decision table and the
focused lifecycle verification recipe.
