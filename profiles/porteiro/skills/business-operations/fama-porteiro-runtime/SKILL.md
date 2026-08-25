---
name: fama-porteiro-runtime
description: "Verifique se um contato é corretor ativo e devolva handoff estruturado ao CEO."
license: MIT
metadata:
  version: 1.0.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, porteiro, corretor, kanban]
---

# Workflow do Porteiro

1. Confirme que o cartão contém correlação, pedido e telefone necessário à
   consulta, ou uma fixture interna com `test_mode: true`.
2. Em modo real, use apenas fonte de identidade autorizada. Como o MCP não está
   configurado nesta fase, bloqueie com kind `capability`; não classifique.
3. Em modo sintético, leia `fixture.decision` e `fixture.entities`, valide que
   a decisão é `active_broker`, `not_active` ou `indeterminate` e não faça
   chamadas externas.
4. Conclua com summary sem telefone e metadata contendo `status`, `decision`,
   `entities`, `evidence`, `reason` e `requested_next_action: return_to_ceo`.
5. Nunca preencha `response_ready` com mensagem externa; use `null`.

Se a entrada estiver incompleta, use `kanban_block` com kind `needs_input`.
Se a dependência autorizada estiver ausente, use kind `capability`.
