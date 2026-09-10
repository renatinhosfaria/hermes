---
name: fama-cadastro-runtime
description: "Use when Cadastro processes a post-Porteiro Kanban task."
license: MIT
metadata:
  version: 1.3.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, cadastro, cliente, lead, kanban]
---

# Workflow do Cadastro

## Entrada e escolha do modo

1. Leia o cartão atual com `kanban_show({})`. Confirme o resultado anterior
   `not_active` do Porteiro, correlação e origem. Um resumo não substitui o cartão.
2. Escolha o ramo antes de chamar qualquer MCP. `test_mode: true` exige fixture
   interna explícita; declaração ambígua ou fixture inválida não autoriza modo real.
3. Dados essenciais ausentes no cartão: `kanban_block(kind="needs_input")`.
   Não solicite telefone ao contato nem derive identidade do texto recebido.

## Ramo sintético

Use apenas `fixture.decision` (ou `fixture.cadastro.decision`) com
`existing_client`, `new_lead` ou `indeterminate`. Copie somente entidades
sintéticas declaradas (`client_id`/`lead_id`); seus IDs devem ter prefixo
`client-`, `lead-`, `synthetic-` ou `test-` (também aceita `_`) e sufixo
alfanumérico, `_` ou `-`, de 1 a 80 caracteres.

Não chame Brain nem FamaChat, não crie registros e não percorra o ramo real.
Conclua pelo handoff abaixo; o guard valida a fixture e produz `TEST_MODE`.

## Ramo real

Leia integralmente [o contrato operacional](references/contrato-cadastro.md)
antes de consultar ou criar. Ele é a fonte canônica para critério comercial,
normalização, paginação, payloads e prova de criação.

Execute em sequência, aguardando cada resultado:

1. Resolva o telefone por `conversation_phone({})` no MCP Brain, mesmo quando
   existir telefone no cartão. Somente `status: ok` com telefone único é prova.
2. Consulte candidatos no FamaChat e complete a paginação segundo o contrato.
3. Aplique o critério sobre telefones completos: um cliente elegível significa
   `JA_E_CLIENTE`; mais de um significa `INCONCLUSIVO`, sem criar.
4. Ausência comprovada: leia `contexto.ctwa_attributions` e siga a identificação
   do empreendimento no contrato. Atribuição confirmada permite buscar por nome
   e ler o candidato único por ID. Sem identificação segura, crie sem vínculo.
5. Ausência comprovada exige criar na mesma execução e confirmar por leitura
   independente. Limite: um POST, inclusive após timeout; até três releituras.
6. Só reporte `LEAD_NOVO_CADASTRADO` depois da confirmação completa, incluindo
   `idEmpreendimento` quando enviado no POST. A pendência de identificação de
   empreendimento, antes do POST, não impede criar sem vínculo.

Nas capacidades obrigatórias de identidade/cliente, capability ausente, MCP
indisponível ou telefone não resolvido:
`kanban_block(kind="capability")`. Consulta incompleta, resposta inválida,
ambiguidade entre clientes ou criação/readback não comprovado: `INCONCLUSIVO`.
Se a indisponibilidade ocorrer após o POST, preserve o ID conhecido no resultado
inconclusivo, sem repetir a criação. `needs_input` é reservado a outro dado
necessário realmente ausente da entrada, não à falha da capability de telefone.

## Handoff e verificação

Conclua com `kanban_complete` após terminar o ramo escolhido. No modo real,
a primeira linha é o veredito puro e IDs mínimos; o formato completo está no
contrato. Summary e metadata não contêm telefone, nome ou mensagem bruta.

O plugin `fama-cadastro-guard` substitui summary, result e metadata por evidência
calculada, com `status`, `decision`, `entities`, `evidence`, `reason`,
`response_ready: null`, `requested_next_action: return_to_ceo` e
`validator_version` na evidência. Nunca estime as contagens.

O guard aplica o contrato nos workers identificados; fora deles bloqueia as
ferramentas Brain/FamaChat do fluxo. Um bloqueio significa operação não executada.
Preserve o limite de um POST e não tente contornar a ferramenta. Sem guard
carregado ou sem capacidade aprovada, bloqueie a execução comercial.
