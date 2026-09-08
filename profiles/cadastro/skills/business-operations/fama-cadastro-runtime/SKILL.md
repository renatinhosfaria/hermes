---
name: fama-cadastro-runtime
description: "Use when the Cadastro profile receives a Kanban task after Porteiro to identify an existing client or register a new lead and return evidence to CEO."
license: MIT
metadata:
  version: 1.1.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, cadastro, cliente, lead, kanban]
---

# Workflow do Cadastro

1. Leia o cartão atual com `kanban_show({})`. Exija o resultado anterior `not_active`, correlação, origem e os
   dados mínimos de identidade, ou fixture interna com `test_mode: true`.
2. Em modo real, mesmo com telefone no cartão, chame sempre
   `conversation_phone()` pelo MCP `brain` com `{}` e sem argumento de
   identidade. Use somente o telefone retornado com `status: ok`; nunca derive
   telefone de nome, texto, LID, `session_key` ou caminho de arquivo. Se a
   capability estiver ausente, indisponível ou não resolver um telefone único,
   use `kanban_block(kind="capability")` e não classifique nem crie cadastro.
3. Com o telefone comprovado, chame `fc_get_clientes` com search igual aos
   últimos quatro dígitos, dentro de `query`. O plugin `fama-cadastro-guard`
   compara os telefones completos nas respostas originais. Ele distingue
   `candidates_returned`, `normalized_matches` e `active_broker35_matches`.
   Quatro candidatos por sufixo podem ter zero telefones correspondentes.
   Se a página vier cheia, incremente `page` mantendo `search` e `pageSize`
   até uma página curta, inclusive vazia. `pagination.total` não é total da
   base. Não refine com telefone sem pontuação e não estime contagens.
4. Se algum candidato satisfizer o critério, o veredito é JA_E_CLIENTE. NÃO crie
   nada: registro existente nunca é alterado nem reativado. Basta um candidato
   para decidir, independente de quantos arquivados existam ao lado. Mais de
   um cliente Reno correspondente é INCONCLUSIVO para conferência.
5. Se nenhum candidato satisfizer o critério, crie o cliente com
   fc_post_clientes — `body` com phone exatamente como retornou do Brain,
   fullName, brokerId: 35, source: "Facebook Ads", sem status.
   O plugin bloqueia o POST sem consulta completa, com cliente Reno existente
   ou após uma tentativa anterior, inclusive se houve timeout. Não repita.
6. Releia o registro com fc_get_clientes_by_id usando o id devolvido: imediato,
   depois ~1s, depois ~1s. Sucesso exige id exato, telefone completo equivalente,
   brokerId 35 e status Sem Atendimento juntos. A resposta do POST não serve como prova. Três
   leituras sem prova é INCONCLUSIVO com o id na frase — não repita o POST e
   não mande para o reno.

   Use kanban_block(kind="capability") só se o MCP não responder, e
   `kind="needs_input"` somente para outro dado realmente ausente que a tarefa
   exija. Nunca classifique sem consulta, e nunca reporte cadastro que não
   aconteceu.
7. Em modo sintético, aceite apenas `existing_client`, `new_lead` ou
   `indeterminate` em `fixture.decision`; copie apenas IDs sintéticos declarados.
8. Conclua com summary sem PII e metadata com `status`, `decision`, `entities`,
   `evidence`, `reason`, `response_ready: null` e
   `requested_next_action: return_to_ceo`.

   Complete após terminar as consultas e o readback necessário. O plugin
   substitui summary, result e metadata por um handoff calculado das respostas
   observadas, incluindo as três contagens e `validator_version`. Sem prova
   suficiente, ele devolve INCONCLUSIVO. Use ferramentas em sequência; aguarde
   cada resultado antes da próxima chamada. Bloqueio do guard é uma operação
   não executada: siga a indicação da ferramenta e preserve o limite de um POST.

   Em modo real, decision assume JA_E_CLIENTE, LEAD_NOVO_CADASTRADO ou
   INCONCLUSIVO — os mesmos vereditos do SOUL.md, e a primeira linha da
   conclusão é sempre o veredito puro, sem prosa antes. O vocabulário
   existing_client / new_lead / indeterminate vale SOMENTE em modo sintético.
9. Nunca faça atendimento comercial ou envie mensagem externa.
