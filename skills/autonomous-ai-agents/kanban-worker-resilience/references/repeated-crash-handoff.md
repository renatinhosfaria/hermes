# Repeated-crash handoff reference

For CEO WhatsApp, these status phrases are internal-only. Use `[SILENT]`
externally and follow `fama-ceo-runtime` for incident reporting. A running retry
is not a definitive failure.

## Decision table

| Observation | Action | Authorized internal wording |
|---|---|---|
| One crash and dispatcher retries | Inspect the existing card; do not duplicate it | “A tentativa falhou internamente; a fila está tratando a retentativa.” |
| Several crashes, no summary/metadata/evidence | Comment the card and preserve dispatcher state; capability blocking requires verified missing capability | “Não há resultado validado; a execução interna precisa ser corrigida.” |
| Clean handoff with incomplete or indeterminate domain result | Follow the handoff contract; do not reinterpret it | Preserve the specialist’s validated status and uncertainty. |
| Verified repair or qualified reassignment | Retry the existing card only | Report only after a readable, evidence-backed handoff exists. |

## Minimal audit comment

“Worker failed repeatedly without producing a handoff or evidence. No validated result is available. Preserve this card; retry only after execution repair or qualified reassignment.”

## Acceptance check

Before reporting success, verify that the card has a completed run and a structured handoff. A `spawned`, `claimed`, `retrying`, or `gave_up` event alone is never a domain result.
