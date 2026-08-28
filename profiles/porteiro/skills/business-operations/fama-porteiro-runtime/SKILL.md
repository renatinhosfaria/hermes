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

1. Confirme que o cartão contém correlação e pedido, ou uma fixture interna com
   `test_mode: true`.
2. Em modo real, se o cartão não trouxer telefone comprovado, chame
   `conversation_phone()` pelo MCP `brain` com `{}` e sem argumento de
   identidade. Use somente o telefone retornado com `status: ok`; nunca derive
   telefone de nome, texto, LID, `session_key` ou caminho de arquivo. Se a
   capability estiver ausente, indisponível ou não resolver um telefone único,
   use `kanban_block(kind="capability")` e não classifique.
3. Com o telefone comprovado, chame `fc_get_users` do MCP `famachat` e
   correlacione localmente pelo campo `phone`, com a normalização do SOUL.md.
   Corretor ativo é qualquer usuário com `isActive = true` cujo telefone bata,
   independente de cargo ou departamento; havendo ativo e inativo com o mesmo
   telefone, vale o ativo. Consulta bem-sucedida sem correspondência é
   `NAO_CORRETOR`.
4. Em modo sintético, leia `fixture.decision` e `fixture.entities`, valide que
   a decisão é `active_broker`, `not_active` ou `indeterminate` e não faça
   chamadas externas.
5. Conclua com `kanban_complete`. A primeira linha deve ser apenas o veredito
   puro, sem prosa antes dele, usando somente `CORRETOR_ATIVO`, `NAO_CORRETOR`
   ou `INCONCLUSIVO`; depois inclua a evidência mínima: cargo, departamento e
   quantos registros casaram. Retorne ao CEO `status`, `decision`, `entities`,
   `evidence`, `reason` e `requested_next_action: return_to_ceo`, sem telefone,
   mensagem bruta ou PII desnecessária em `summary` ou `metadata`.
6. Nunca preencha `response_ready` com mensagem externa; use `null`.

`INCONCLUSIVO` só é permitido quando a consulta não rodou (MCP fora do ar,
erro da ferramenta ou resposta quebrada) ou quando houver dois registros ativos
com o mesmo telefone e dados conflitantes.
