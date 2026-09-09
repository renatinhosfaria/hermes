# Learning persistence verification

## Destination decision table

| Signal | Destination | Do not use |
|---|---|---|
| Stable user identity, preference, expectation, or environment fact | `memory` | A session-only note or a procedural skill |
| Reusable sequence, command, decision point, pitfall, or acceptance check | Class-level skill | User memory as a substitute for procedure |
| Temporary state, raw transcript, third-party PII, secret, hypothesis, or unverified method | Nothing | Either persistent store |

## Review sequence

1. Enumerate skills with `skills_list`.
2. Reload the candidate with `skill_view`; inspect linked topical files before
   editing an existing file.
3. Reuse an editable class-level target before creating a new umbrella.
4. Make one consolidated `memory` call for user facts and one atomic
   `skill_manage` operation batch for skill changes.
5. Reload the changed skill and confirm the returned content.

## Lifecycle boundaries

- `memory.nudge_interval` counts user turns.
- `skills.creation_nudge_interval` counts tool iterations.
- The native review fork requires a clean final response and available learning
  tools.
- The CLI finalization hook must wait for background review before cleanup, up
  to 300 seconds; gateway review is asynchronous.

## Persistence criterion

A resolved setting or enabled feature is not persistence evidence. A valid
check creates or changes the target, terminates the writer, and recovers both
memory and skill from an independent process in the same profile. Include
profile/channel isolation and timeout behavior when those are part of the
claim. Do not record a workflow as reliable when no working path was actually
verified.
