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
2. Em modo real, chame fc_get_clientes com search igual aos últimos quatro
   dígitos do telefone. Correlacione localmente com a normalização do SOUL.md, e
   aplique o critério: brokerId == 35 e status != "Arquivado".
3. Se nenhum candidato satisfizer o critério, crie o cliente com
   fc_post_clientes — phone, fullName, brokerId: 35, source: "Facebook Ads",
   sem status. Confira brokerId == 35 no retorno antes de reportar sucesso.

   Use kanban_block(kind="capability") só se o MCP não responder, e
   kind="needs_input" se o cartão não trouxer telefone. Nunca classifique sem
   consulta, e nunca reporte cadastro que não aconteceu.
4. Em modo sintético, aceite apenas `existing_client`, `new_lead` ou
   `indeterminate` em `fixture.decision`; copie apenas IDs sintéticos declarados.
5. Conclua com summary sem PII e metadata com `status`, `decision`, `entities`,
   `evidence`, `reason`, `response_ready: null` e
   `requested_next_action: return_to_ceo`.
6. Nunca faça atendimento comercial ou envie mensagem externa.
