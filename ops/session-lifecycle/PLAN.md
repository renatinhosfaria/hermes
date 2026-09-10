# Encerramento de sessões WhatsApp por inatividade

Escopo autorizado: encerrar sessões DM do CEO após 90 dias sem entrada externa
ou saída confirmada, sem apagar histórico, enviar mensagens ou alterar o core.

Arquitetura: scanner somente leitura + plugin local executor. O scanner roda
fora do loop; a decisão final roda sincronamente no loop do gateway, sem await,
após verificar fila/adapters/turnos, reler bancos e adquirir lease nativa.
Somente `promote_to_session_reset(sid, reason="idle")` fecha a sessão. O gateway
reconcilia sua rota na próxima entrada. O adaptador privado é isolado e exige
hashes iguais aos módulos instalados validados; divergência impede aplicação.

- [x] Testar seleção com fixtures: 89/90 dias, saída confirmada, silêncio,
  notificações, tarefa pendente, entrega pendente, sessão pausada, outra plataforma.
- [x] Implementar scanner e coleta durável de tempos de saída (ledger tem retenção curta).
- [x] Testar promoção nativa, preservação do transcript e recuperação em nova sessão.
- [x] Implementar executor com guardas de concorrência, compatibilidade e exclusão mútua.
- [x] Testar atividade surgindo entre scan e apply; fila anterior à criação do agente.
- [x] Instalar plugin somente no CEO e desabilitar auto_prune somente no state.db do CEO.
- [x] Executar dry-run, validação de política Git, testes e restart nativo para carregar plugin.

Ausência de comprovação histórica de envio: timestamp de resposta final antiga
é usado apenas como barreira conservadora (pode adiar encerramento, nunca
antecipar). Eventos internos classificados e SILENT não reiniciam o relógio.
Somente o horário e SID são mantidos no banco próprio, sem texto/telefone.
Sessões sem qualquer entrada externa comprovada não são candidatas.

Manutenção administrativa, pausa humana, envio pendente e tarefas não terminais
impedem encerramento. O plugin nunca retoma pausa nem responde ao contato.
O período é verificado diariamente; atividade impede apply e provoca nova
tentativa posterior. Erro de schema/API/compatibilidade falha fechado.

Retenção: auto_prune do CEO fica explicitamente falso. Nenhuma limpeza manual
é executada. O histórico permanece para o Brain, sujeito às autorizações dele.
