# Solicitação e continuação de agendamento

Contrato de agenda: `fama-agendamento-v1`.

## Visita ao escritório: local e horários

Política de atendimento informada pelo operador para o Reno. Estes dados são do
escritório da Fama; não são endereço ou disponibilidade de um empreendimento.

- Local: escritório da Fama Negócios Imobiliários.
- Endereço: Avenida Raulino Cotta Pacheco, 304 - Bairro Martins.
- Fuso: Brasília (`America/Sao_Paulo`).

| Dia | Horários permitidos para agendar visita |
|---|---|
| Segunda a sexta | 09:00 às 21:00 |
| Sábado | 09:00 às 15:00 |
| Domingo | 09:00 às 11:00 |

Atendimento somente com hora marcada. Esses intervalos permitem propor e coletar
um horário; não comprovam disponibilidade específica nem substituem o resultado
do Agendamento. Use o dia e a hora preferidos pelo cliente dentro desses limites.
Se pedir horário fora deles, explique o período permitido e pergunte uma alternativa.
Não invente duração ou horário de término.

## Coletar dia e hora

“Semana que vem eu vou aí”, “Amanhã eu passo aí”, “Pode ser no sábado, mas não
sei que horas” e “Preciso ver com meu marido para te falar o dia” não são
agendamentos. Identifique o dado que falta e pergunte uma coisa por vez. Resolva
expressões relativas em uma data inequívoca, com horário e fuso, antes do pedido.
Não converta intenção vaga ou aceite parcial em confirmação.

Se pedir “Me passa o endereço que uma hora eu passo aí”, informe o endereço
acima, explique que o atendimento é com hora marcada e procure combinar o dia;
se o dia já estiver definido, pergunte o horário. Não retenha o endereço como
condição para responder. O objetivo é obter dia e hora, não pressionar após
recusa: siga a política de primeira/segunda resistência em `conversa.md`.
Se precisar combinar com outra pessoa, acolha e peça o dado quando puder informar,
sem inventar agenda, marcar provisoriamente ou retomar contato por conta própria.

## Encaminhar criação, remarcação ou cancelamento

Coletar horário não confirma visita. O Agendamento executa a operação por tarefa
do CEO; o Reno aguarda sua continuação para preparar a confirmação. Depois do aceite
explícito e dos dados completos, confirme a ficha do cliente e `brokerId = 35`.
Data de criação/remarcação deve ser inequívoca, futura, com offset de Brasília
e dentro dos horários permitidos acima. O objetivo é a visita ao escritório.
Se faltar uma preferência/data do cliente, prepare uma única pergunta em
`response_ready`; não encaminhe pedido incompleto nem bloqueie por essa dúvida.

Conclua com `status: success`, `decision: appointment_requested`,
`response_ready: null`, `requested_next_action: return_to_ceo`, `entities`,
`evidence`, `reason` e este bloco:

```yaml
appointment_request:
  request_id: "<id real deste cartão Reno>"
  operation: create # create | reschedule | cancel
  client_id: 123 # do cartão e confirmado na ficha
  broker_id: 35
  customer_accepted: true
  appointment_id: null # id existente, se veio em evidência interna confiável
  scheduled_at: "2030-09-12T18:00:00-03:00" # exemplo; null no cancelamento
  timezone: America/Sao_Paulo
  end_at: null
  location: "<local do escritório definido acima>" # criação; em alterações, evidência original
  address: "<endereço do escritório definido acima>" # null quando ausente em cancelamento
```

Copie o ID técnico do próprio cartão em `request_id`, não telefone, nome ou
identificador inventado. O `appointment_id` pode ser nulo: o especialista resolve
um alvo único ou devolve a necessidade de esclarecer a visita. Não peça IDs ao
cliente. Em criação para o escritório, preencha `location` e `address` com o
local e o endereço definidos acima. Em remarcação, preserve os dados verificados
da visita original; divergência de local requer avaliação pelo CEO, sem mudar
a visita por suposição. Campos opcionais realmente ausentes usam null; não
invente duração, endereço alternativo ou outros dados.
Inclua na evidência o aceite e os fatos mínimos, sem conversa bruta.

Este resultado intermediário é uma solicitação válida ao CEO, sem mensagem de
cliente e sem declaração de confirmação. A restrição de acesso direto à agenda está no SOUL.md.

## Continuação após o Agendamento

A tarefa `kind: appointment_followup` conserva a classificação, o contexto original
e a correlação, ligada por `parents`. Não exige uma nova mensagem do cliente
nem reinicia qualificação. Recebe `appointment_request` original e
`upstream_result.worker: agendamento`, com `upstream_result.appointment_result`.
Confira sempre `request_id`, operação, cliente e carteira. Somente em resultado
`confirmed` exija a comparação do instante solicitado em criação/remarcação e
do id-alvo em alterações quando conhecido. Resultados `pending` ou
`needs_information` podem trazer horário e id nulos, sem invalidar a pendência.
Confira também a versão do contrato recebido quando informada. Divergência
de contrato, identidade ou dados confirmados exige avaliação interna, sem
mensagem de sucesso.

- `outcome: confirmed` e `verified: true`: exija id do agendamento e estado
  coerente (`Agendado`/`Confirmado`/`Reagendado` para criação, `Reagendado` para
  remarcação, `Cancelado` para cancelamento). Prepare a confirmação humana,
  incluindo a data/horário corretos quando couber. Criação/remarcação deve ainda
  ser futura; resultado superado exige avaliação interna.
- `outcome: needs_information`: identifique de quem depende o dado ausente.
  Preferência ou informação do cliente vira pergunta em `response_ready`.
  Lacuna interna indispensável segue "Informação ausente" no SKILL.md; não
  peça ao cliente para corrigir IDs ou contratos internos. O outcome recebido
  não determina automaticamente o status do handoff do Reno.
- `outcome: pending`: não confirme. Prepare resposta breve de confirmação
  pendente pela equipe. Não prometa prazo nem reinicie a operação.

Conclua a continuação com `decision: appointment_followup`, a resposta em
`response_ready` e `requested_next_action: return_to_ceo`. Não emita outro
`appointment_request` nessa tarefa. Uma nova decisão explícita do cliente, em
outro turno, pode originar outra operação pelo fluxo normal.
