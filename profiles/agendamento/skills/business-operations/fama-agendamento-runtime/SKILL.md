---
name: fama-agendamento-runtime
description: "Use nas tarefas do Agendamento para criar, remarcar ou cancelar visitas no FamaChat encaminhadas pelo CEO."
metadata:
  version: 1.0.1
  author: Fama Negócios Imobiliários
---

# Operações de agendamento

A conferência é parte das operações `create`, `reschedule` e `cancel`, incluindo
reconciliação por leitura. Este contrato não define uma operação independente
de consulta. Não transforme um pedido de consulta em escrita.

## 1. Reconhecer a solicitação

Leia o cartão completo com `kanban_show`, incluindo `upstream_result`, pedido original,
correlação, comentários e tentativas anteriores. A entrada vem em `upstream_result.appointment_request`; o CEO também
pode transportá-la em `appointment_request`. Se ambos existirem, devem ser iguais.
O cartão fornece o pedido e os identificadores internos; o FamaChat fornece o
estado atual. Não derive IDs de nomes, telefones ou texto recebido, nem reutilize
dados de outra conversa.
O pedido tem esta forma (opcionais usam `null`, nunca dados inventados):

```yaml
appointment_request:
  request_id: "<id da tarefa original do Reno>"
  operation: create # create | reschedule | cancel
  client_id: 123 # inteiro positivo fornecido pelo cartão
  broker_id: 35
  customer_accepted: true
  appointment_id: null # id-alvo, quando conhecido
  scheduled_at: "2030-09-12T18:00:00-03:00" # exemplo; null para cancelamento
  timezone: America/Sao_Paulo
  end_at: null
  location: null
  address: null
```

`request_id` é copiado da tarefa original do Reno; não gere outro em retentativas
ou continuações. Verifique a correlação do cartão e os IDs de `entities` quando
presentes. Divergência impede a operação; nunca escolha um dos IDs arbitrariamente.

Exija `customer_accepted: true`, cliente e corretor identificados e operação
conhecida. Para criar/remarcar, exija data e horário inequívocos, com offset e
futuros em `America/Sao_Paulo`. Não interprete "quinta às 18h" por conta própria.
Campos opcionais ausentes não bloqueiam. `end_at`, quando fornecido, deve ser
posterior ao início; local/endereço vêm de fatos do pedido.

Falta de preferência/aceite/data que só o cliente pode esclarecer resulta em
`needs_information` para retorno ao Reno. Identificadores ou correlação internos
ausentes/divergentes exigem avaliação interna e impedem escrita.

## 2. Conferir cliente e registro

Leia `fc_get_clientes_by_id(id=client_id)`. Confira retorno completo, id exato e
`brokerId = 35`. Outra carteira não recebe nenhuma escrita comercial.
Falha, truncamento ou resposta ambígua não comprovam identidade nem inexistência.

| Ferramenta comercial autorizada | Finalidade |
|---|---|
| `fc_get_clientes_by_id` | Verificar cliente e carteira |
| `fc_get_appointments` | Buscar com `query: {clienteId: client_id, brokerId: 35}` |
| `fc_get_appointments_by_id` | Ler alvo ou conferir após a escrita |
| `fc_post_appointments` | Criar uma visita |
| `fc_patch_appointments_by_id` | Remarcar ou cancelar o mesmo registro |

Não liste toda a agenda sem filtro, não use PUT/DELETE, não consulte outros
clientes e não procure alternativas em terminal, arquivo, SQLite ou HTTP direto.
O contrato atual da listagem devolve uma lista completa filtrada. Só conclua
ausência ou unicidade com esse conjunto completo: saída truncada, indicação de
mais páginas ou formato parcial sem completude comprovada resulta em pendência.
Não invente parâmetros de paginação nem trate a primeira página como toda a lista.

Se um id-alvo veio no pedido, leia-o e confira `clienteId`, `brokerId` e
`type = Visita`. Antes de buscar candidatas em remarcação/cancelamento sem id,
procure o marcador `APPOINTMENT_ATTEMPT` desse `request_id`. Se existir, recupere
dele o `appointment_id` resolvido e o body enviado, conferindo operação, cliente
e carteira. Faça somente a releitura desse alvo, inclusive se já estiver
`Cancelado`; não selecione outra visita ativa. Marcadores conflitantes ou alvo
ausente após uma tentativa exigem pendência interna, nunca nova seleção/escrita.
Sem id e sem tentativa anterior, busque as visitas do cliente:
se houver uma única visita ativa futura compatível com a evidência do pedido,
leia-a pelo id. Múltiplas candidatas exigem esclarecimento pelo CEO/Reno.
Não peça ao cliente IDs internos; peça um dado compreensível, como a data da visita.

Status ativos: `Agendado`, `Confirmado`, `Reagendado`. Visita passada, em andamento,
concluída ou com não comparecimento exige avaliação interna. Um registro já
cancelado pode satisfazer cancelamento após conferir identidade; nunca reative
um cancelado para atender criação ou remarcação.

## 3. Evitar repetição de escrita

Antes de criar, busque visitas do mesmo cliente/corretor. Um equivalente tem
tipo `Visita`, status ativo, mesmo instante de início e compatibilidade com todos
os opcionais efetivamente solicitados. Leia o único equivalente pelo id e
reutilize-o; não crie outro. Múltiplos equivalentes ou dados conflitantes exigem
avaliação interna. Em remarcação/cancelamento, estado já igual ao pedido pode
ser reconhecido após releitura, sem repetir PATCH.

Antes de qualquer POST/PATCH, grave no próprio cartão, por `kanban_comment`, uma
linha `APPOINTMENT_ATTEMPT ` seguida de JSON com `request_id`, `operation`,
`client_id`, `broker_id`, `appointment_id` resolvido e o `body` exato a enviar.
Não inclua conversa bruta ou credenciais. Confira que o comentário foi salvo;
se falhar, não escreva no FamaChat.

Havendo marcador anterior para esse pedido — inclusive transportado pelo CEO —,
faça somente reconciliação por leitura. Nunca emita nova escrita automática,
mesmo se uma leitura vazia vier depois de timeout: ausência de registro visível
não prova que a tentativa anterior não será efetivada.

Se pedido e marcador divergirem, devolva pendência interna. Não invente outro
`request_id`, cartão ou cliente para contornar a tentativa. O CEO serializa
operações equivalentes; esta disciplina não constitui garantia atômica contra
gravações concorrentes no servidor.

## 4. Executar uma operação

### Criar

Após as conferências e o marcador, chame `fc_post_appointments` uma vez, com:

```json
{"body":{"clienteId":123,"brokerId":35,"type":"Visita","status":"Agendado","scheduledAt":"2030-09-12T18:00:00-03:00"}}
```

Exemplo sintético: substitua pelos dados comprovados. Inclua `endAt`, `location`
e `address` somente quando informados. No body da API use `clienteId`, não
`client_id`. Exija resposta 201 com id e faça releitura por esse id.
Não repita os efeitos automáticos do FamaChat: não escreva manualmente em
cadastro, funil, notas, SLAs ou outros registros.

### Remarcar

Leia o alvo imediatamente antes de preparar a alteração. Preserve id, cliente,
corretor, tipo, local, endereço e demais campos. O PATCH contém somente
`scheduledAt`, `status: Reagendado` e `endAt` quando necessário.
Com início e término anteriores, mantenha a duração: novo término = novo início
+ duração anterior. Pedido de duração diferente exige avaliação, sem alteração
silenciosa. Sem término anterior, preserve `null`.

Compare com o estado lido anteriormente; mudança inesperada exige avaliação,
não sobrescrita. O endpoint de agendamentos não aceita `expectedStatus`: não copie
o contrato de atualização de clientes. Após o marcador, execute um PATCH e releia.

### Cancelar

Após ler/conferir o alvo e salvar o marcador, chame
`fc_patch_appointments_by_id(id=appointment_id, body={"status":"Cancelado"})`.
Não apague, não crie substituição e não mude a data. Releia pelo id.

## 5. Conferir e devolver

POST/PATCH não substitui releitura. Confira no GET pelo id: identificador exato,
`clienteId`, `brokerId = 35`, tipo `Visita`, início (e término, quando aplicável),
local/endereço solicitados e status esperado. Compare instantes com offset,
não apenas a aparência das strings.

Criar/remarcar só é confirmado se continuar futuro. Criação aceita `Agendado`
ou, ao reutilizar equivalente, outro status ativo; remarcação exige `Reagendado`;
cancelamento exige `Cancelado`. Inconsistência, truncamento ou falha de releitura
resulta em pendência. Não repita escrita para corrigir sem novo fluxo.

Entregue por `kanban_complete`, com resumo interno curto sem PII e metadata:

```yaml
status: success
decision: appointment_processed
entities: {client_id: 123, appointment_id: 456}
response_ready: null
requested_next_action: return_to_ceo
reason: "Registro conferido pelo id."
evidence: ["GET por id conferiu cliente, carteira, tipo, horário e status."]
appointment_result:
  request_id: "<id da tarefa original do Reno>"
  operation: create
  client_id: 123
  broker_id: 35
  outcome: confirmed # confirmed | pending | needs_information
  appointment_id: 456
  scheduled_at: "2030-09-12T18:00:00-03:00"
  status: Agendado # estado realmente relido
  verified: true
  reason: "Registro conferido pelo id."
```

`status: success` externo significa que a tarefa devolveu um resultado válido;
somente `appointment_result.outcome: confirmed` com `verified: true` confirma a
operação comercial. `pending` e `needs_information` usam `verified: false` e
descrevem o que falta. Campos não comprovados usam `null`; não declare horário ou
id verificados com base apenas em intenção. Inclua em `evidence` a tentativa
salva e a reconciliação realizada, quando houver.

O CEO devolve o resultado ao Reno; você nunca escreve uma mensagem de cliente.
Em erro de contrato/identidade interna, use um único bloqueio `needs_input`
explicando o dado interno ausente. Não repita bloqueios nem crie tarefa paralela.

## Testes

Em `test_mode: true`, use exclusivamente os dados sintéticos do cartão e as
ferramentas simuladas explicitamente fornecidas. Sem simuladores, descreva a
decisão sem chamar MCPs ou serviços reais. Simulação nunca confirma uma operação real.

Ao validar mudanças nesta skill, distinga revisão documental, testes offline e
simulação com modelo. Nenhuma dessas verificações comprova escrita em produção.
