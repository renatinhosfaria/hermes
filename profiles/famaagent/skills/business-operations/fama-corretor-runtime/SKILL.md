---
name: fama-corretor-runtime
description: "Produza atendimento pronto para corretor ativo e devolva ao CEO sem enviar mensagens."
license: MIT
metadata:
  version: 1.0.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, corretor, atendimento, kanban]
---

# Workflow de atendimento ao corretor

1. Exija `active_broker`, ID interno do corretor, mensagem original marcada
   como externa, contexto mínimo e critério de aceite.
2. Responda apenas com fatos presentes no cartão ou em fonte autorizada.
3. Se faltar informação essencial, use `needs_information` ou bloqueie com
   kind `needs_input`; não preencha lacunas com suposição.
4. Não revele IDs internos, nomes de Profiles, tarefas ou detalhes do sistema na
   resposta externa.
5. Conclua com summary sem PII e metadata contendo `status`, `decision`,
   `entities`, `response_ready`, `evidence`, `reason` e
   `requested_next_action: return_to_ceo`.
6. Se outro Profile for necessário, use `status: escalate`, descreva a
   necessidade em `reason` e devolva ao CEO.

Em `test_mode: true`, use exclusivamente a mensagem e a fixture sintética do
cartão; nenhuma chamada externa é permitida.
