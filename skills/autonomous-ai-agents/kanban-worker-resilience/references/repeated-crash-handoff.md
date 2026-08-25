# Repeated-crash handoff reference

## Decision table

| Observation | Action | External wording |
|---|---|---|
| One crash and dispatcher retries | Inspect the existing card; do not duplicate it | “A tentativa falhou internamente; a fila está tratando a retentativa.” |
| Several crashes, no summary/metadata/evidence | Comment the card and keep it blocked for capability | “Não há resultado validado; a execução interna precisa ser corrigida.” |
| Clean handoff with incomplete or indeterminate domain result | Follow the handoff contract; do not reinterpret it | Preserve the specialist’s validated status and uncertainty. |
| Verified repair or qualified reassignment | Retry the existing card only | Report only after a readable, evidence-backed handoff exists. |

## Minimal audit comment

“Worker failed repeatedly without producing a handoff or evidence. No validated result is available. Preserve this card; retry only after execution repair or qualified reassignment.”

## Acceptance check

Before reporting success, verify that the card has a completed run and a structured handoff. A `spawned`, `claimed`, `retrying`, or `gave_up` event alone is never a domain result.
