---
name: fama-cadastro-runtime
description: "Classifique cliente ou lead novo e devolva handoff estruturado ao CEO."
license: MIT
metadata:
  version: 1.0.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, cadastro, cliente, lead, kanban]
---

# Workflow do Cadastro

1. Exija no cartão o resultado anterior `not_active`, correlação, origem e os
   dados mínimos de identidade, ou fixture interna com `test_mode: true`.
2. Em modo real, use somente fonte autorizada. Sem MCP nesta fase, bloqueie com
   kind `capability`; não crie nem classifique registro.
3. Em modo sintético, aceite apenas `existing_client`, `new_lead` ou
   `indeterminate` em `fixture.decision`; copie apenas IDs sintéticos declarados.
4. Conclua com summary sem PII e metadata com `status`, `decision`, `entities`,
   `evidence`, `reason`, `response_ready: null` e
   `requested_next_action: return_to_ceo`.
5. Nunca faça atendimento comercial ou envie mensagem externa.

Entrada incompleta usa `kanban_block` kind `needs_input`. Dependência ausente
usa kind `capability`.
