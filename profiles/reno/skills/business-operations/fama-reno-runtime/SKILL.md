---
name: fama-reno-runtime
description: "Produza a próxima resposta comercial para cliente ou lead e devolva ao CEO."
license: MIT
metadata:
  version: 1.0.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, reno, cliente, lead, atendimento, kanban]
---

# Workflow comercial do Reno

1. Exija `existing_client` ou `new_lead`, ID interno, mensagem original,
   contexto mínimo e critério de aceite.
2. Se o resultado anterior for `LEAD_NOVO_CADASTRADO`, chame `conversation_recent`
   uma vez — exatamente uma — antes de escrever qualquer coisa. Se falhar, não
   repita na mesma execução: siga e registre em `evidence` que o histórico não
   foi recuperado.
3. Produza uma única próxima resposta, curta, humana e adequada ao estágio do
   atendimento.
4. Faça no máximo as perguntas necessárias para avançar; não repita dados já
   presentes no cartão.
5. Não prometa disponibilidade, preço, prazo, visita ou condição sem fato ou
   autorização explícita.
6. Conclua com summary sem PII e metadata contendo `status`, `decision`,
   `entities`, `response_ready`, `evidence`, `reason` e
   `requested_next_action: return_to_ceo`.
7. Necessidade de outro especialista usa `status: escalate` e retorna ao CEO.

Em `test_mode: true`, opere somente sobre os dados sintéticos do cartão e não
faça chamadas externas.
