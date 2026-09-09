# Incidentes e recuperação de entrega

## Quando o worker falhar

Sem resposta válida do especialista, mantenha silêncio no WhatsApp: finalize
com `[SILENT]`, sem aviso de falha, desculpa, frase de espera ou texto próprio.
Essa é a política de atendimento; a pendência deve chegar ao Renato pelo canal
interno de incidentes, não ao contato externo.

Antes de tratar um wake de `crashed`, `timed_out`, `gave_up` ou bloqueio como
impedimento atual, consulte o cartão e o último run. Uma falha antiga seguida de
retentativa em `ready` ou `running` não é falha definitiva; aguarde o dispatcher.
Não crie tarefa substituta, não force retry e não encerre o atendimento.

Porteiro e Cadastro concluídos com veredito válido e `response_ready: null`
são sucesso normal: continue o roteamento. Também são etapas válidas o Reno com
`decision: appointment_requested` e pedido completo, e o Agendamento com
`decision: appointment_processed` e resultado estruturado válido. Nessas etapas,
`response_ready: null` é esperado: siga a referência `references/agendamento.md` de `fama-ceo-runtime`.
`outcome: pending` exige acompanhamento interno e retorno ao Reno, sem confirmar.
Nos demais casos, Reno/FamaAgent sem resposta válida,
resultado inconclusivo que impeça avançar, bloqueio por capacidade ou triagem
exigem acompanhamento interno. `needs_input` não é por si só falha: diferencie
uma pergunta válida ao contato de uma dependência interna ausente.

Quando houver impedimento real, registre uma vez no cartão afetado, com
`kanban_comment`, uma linha iniciada por `INCIDENTE_ATENDIMENTO `, seguida de
motivo técnico curto, etapa e ação necessária. Antes de registrar, confira se o
mesmo incidente já consta dos comentários. Não inclua nomes, telefones,
mensagens brutas, credenciais ou uma hipótese apresentada como causa.

O canal de incidentes é o Telegram configurado do Dev. O monitor externo
`hermes-fleet-watch.timer` lê os cartões e o histórico a cada cinco minutos,
registra o incidente, envia o alerta pelo bot do Dev e pode solicitar diagnóstico
somente de leitura. Você não precisa enviar Telegram de dentro do WhatsApp.
Se o Kanban ou o próprio CEO falhar, a verificação independente também cobre
indisponibilidade de serviços e mensagens externas sem resposta registrada há
mais de 15 minutos. Nunca afirme que Renato foi avisado sem confirmação de envio.

O monitor controla repetição e entrega; wakes repetidos não autorizam mensagens
ao cliente nem novos cartões. Uma notificação de que o sinal desapareceu não
comprova que o lead foi respondido. A retomada depende de conferir o estado atual,
novas mensagens e eventual atendimento humano. Não reenvie respostas antigas nem
retome automaticamente um contato assumido por humano.

Assunção humana suspende a automação, mas não comprova correção técnica.
Não recrie nem reabra incidente por wake repetido depois de encerramento
registrado por decisão humana. Uma nova falha precisa de evidência nova.

Depois de uma resolução verificada e autorizada, registre no mesmo cartão
`INCIDENTE_ENCERRADO ` com a evidência técnica mínima. O comentário não altera o
estado do cartão nem substitui a correção de um bloqueio real. Se não conseguir
registrar, permaneça em silêncio no WhatsApp; o monitor independente é a proteção
para a falha do próprio barramento.

## Reentrega do gateway não é resposta sua

Uma mensagem que aparece no histórico prefixada com `♻️ Recovered reply` foi
reenviada pelo próprio gateway, não escrita por você agora. O Hermes registra a
resposta final antes de enviá-la; se o processo morre entre o envio e a
confirmação da plataforma, o boot seguinte reenvia com esse aviso, porque é
preferível o contato receber duas vezes a não receber.

Trate isso como entrega já feita, nunca como turno novo. Não responda de novo,
não reescreva o texto e não peça desculpa ao contato pela duplicata — explicar
uma reentrega é expor o funcionamento interno a quem está de fora. O mesmo vale
para o prefixo `♻️ Recovered reply` que menciona reconexão da plataforma.

O marcador está em inglês e vem da instalação do Hermes, que não é alterável.
Ele é raro por construção: só aparece quando o gateway morre de forma não
graciosa dentro da fração de segundo entre enviar e confirmar.
