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
2. Em modo real, chame `list_users` do MCP `famachat` e correlacione localmente
   pelo campo `phone`, com a normalização do SOUL.md. Corretor ativo é qualquer
   usuário com `is_active = true` cujo telefone bata, independente de cargo ou
   departamento; havendo ativo e inativo com o mesmo telefone, vale o ativo.
   Consulta bem-sucedida sem correspondência é `NAO_CORRETOR`. Use
   `kanban_block(kind="capability")` só se o MCP não responder, e
   `kind="needs_input"` se o cartão não trouxer telefone.
3. Em modo sintético, leia `fixture.decision` e `fixture.entities`, valide que
   a decisão é `active_broker`, `not_active` ou `indeterminate` e não faça
   chamadas externas.
4. Conclua com `kanban_complete`. A primeira linha deve ser apenas o veredito
   puro, sem prosa antes dele, usando somente `CORRETOR_ATIVO`, `NAO_CORRETOR`
   ou `INCONCLUSIVO`; depois inclua a evidência mínima: cargo, departamento e
   quantos registros casaram. Retorne ao CEO `status`, `decision`, `entities`,
   `evidence`, `reason` e `requested_next_action: return_to_ceo`, sem telefone,
   mensagem bruta ou PII desnecessária em `summary` ou `metadata`.
5. Nunca preencha `response_ready` com mensagem externa; use `null`.

`INCONCLUSIVO` só é permitido quando a consulta não rodou (MCP fora do ar,
erro da ferramenta ou resposta quebrada) ou quando houver dois registros ativos
com o mesmo telefone e dados conflitantes.
