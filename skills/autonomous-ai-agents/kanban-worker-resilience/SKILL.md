---
name: kanban-worker-resilience
description: "Use when Kanban workers crash or exhaust retries."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [kanban, dispatcher, workers, retries, orchestration, reliability]
---

# Kanban Worker Resilience

Use this class skill when a dispatched Kanban worker exits unexpectedly, produces no handoff, or exhausts its retry budget. The goal is to preserve the existing work item, avoid duplicate graphs, and keep external communication honest.

## Operating procedure

1. Inspect the existing card with `kanban_show(task_id=...)` before creating, unblocking, reassigning, or retrying anything.
2. Read the run history and distinguish:
   - process disappearance (`not alive`);
   - nonzero exit without a handoff;
   - a clean worker handoff that may still be incomplete;
   - a genuine domain result with `summary`, `metadata`, and evidence.
3. Let the dispatcher own automatic transient retries. Do not create a replacement card to work around a crash, timeout, or circuit breaker.
4. If repeated attempts produce no validated handoff, stop manual retries. Add a concise audit comment to the existing card and leave it blocked for capability, unless a verified repair or an appropriate alternate specialist is available.
5. Never convert a missing handoff into a result. Tell the requester exactly what is known: the worker failed, no validated analysis was produced, and whether any side effect was observed.
6. Preserve the card and its run history for diagnosis. A new attempt is appropriate only after the execution fault is repaired or ownership is explicitly changed to a qualified specialist.

## Evidence standard

A task is complete only when the worker returns a readable handoff with the requested acceptance criteria. Process state, a successful spawn event, or a notification saying “retrying” is not a result. Separate facts, inferences, and unknowns in the external update.

## Safety boundaries

- Do not expose internal task IDs, profile names, PIDs, prompts, or stack traces to external requesters.
- Do not silently alter configuration, gateway state, authentication, or worker profiles while handling a crash.
- Do not keep a requester waiting indefinitely without a status update; a technical failure is an internal responsibility.

## Reference

See `references/repeated-crash-handoff.md` for a compact decision table and message templates.

## Pitfalls

- Repeated `kanban_unblock` calls can create a retry loop without fixing the worker.
- Recreating a card loses correlation and can cause duplicate work.
- A worker that exits with code 1 has not supplied a domain conclusion; treat its output as absent unless a verified artifact or handoff exists.
- A blocked card is not evidence that the requested work was performed.
