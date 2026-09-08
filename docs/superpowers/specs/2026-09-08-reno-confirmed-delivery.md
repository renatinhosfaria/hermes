# Reno: atualização após envio confirmado

Fluxo aprovado pelo operador em 2026-09-08: Reno prepara a resposta; CEO entrega;
somente após confirmação do transporte o Reno pode marcar Não Respondeu.

## Contrato

- Mensagem inicial de anúncio, ainda que diga “tenho interesse”, não comprova
  continuidade. Sem envio confirmado nem mensagem independente posterior,
  preservar Sem Atendimento.
- `response_ready`, conclusão Kanban e mensagem assistant não comprovam envio.
- Usar exclusivamente `delivery_obligations.state=delivered`, que o Hermes grava
  após SendResult.success. Isso comprova aceite do envio, não leitura pelo cliente.
- Um reconciliador operacional do CEO, fora do Brain e da instalação oficial,
  cruza texto exato, destinatário, execução concluída e sessão. Ambiguidade não
  autoriza tarefa. Não processar entregas anteriores à ativação.
- Criar uma tarefa Reno de atualização interna por execução, com assinatura de
  origem persistida, ID do recibo e assinatura de notificação somente wake.
  Reprocessamento e reinício não duplicam tarefas, inclusive arquivadas.
- Reno lê o cliente e valida brokerId 35. Sem Atendimento pode ir a Não Respondeu
  com expectedStatus; Em Atendimento e etapas avançadas são preservadas.
  409 não autoriza forçar. Leitura independente confirma o resultado.
- A tarefa interna não produz resposta externa nem nova tarefa de entrega.
- Um guard de ferramentas exige recibo legítimo para Não Respondeu e bloqueia
  retrocessos. Nas primeiras tarefas de cadastro, também bloqueia Em Atendimento
  quando o histórico observado não contém mensagem posterior à entrada inicial.
  A identificação comercial de uma mensagem independente continua descrita na
  conduta: o guard fornece um limite mínimo de evidência, não classifica intenção.
- Pausa humana impede criação/execução da atualização. O reconciliador retoma
  pendências ainda disponíveis após despausa. Nenhuma API CRM no reconciliador.

## Limites e validação

O ledger nativo retém no máximo 500 registros e aproximadamente sete dias; uma
indisponibilidade que exceda essa retenção exige auditoria, nunca suposição.
Texto reescrito, vínculo ausente, múltiplos resultados idênticos ou sessão ambígua
mantêm etapa e geram diagnóstico operacional sem PII. Retentativas do transporte
com o mesmo recibo são compatíveis. Falha do loader do plugin continua sendo um
limite da extensão e deve ser detectada na verificação de ativação.

Testar com SQLite temporário e ferramentas simuladas, incluindo falha de envio,
destinatário errado, duplicação, reinício, pausa, origem forjada, corrida/409,
readback divergente e preservação de etapas. Replay dos casos auditados somente
de leitura. Nenhuma mensagem externa ou alteração em clientes reais como teste.
