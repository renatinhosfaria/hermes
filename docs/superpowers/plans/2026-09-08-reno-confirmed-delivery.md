# Plano: envio confirmado e etapa Reno

**Spec:** ../specs/2026-09-08-reno-confirmed-delivery.md
**Execução:** inline, em worktree isolada; aplicar somente arquivos revisados.

- [x] Testes falhando para reconciliador e guard em bancos temporários.
- [x] Implementar correlação estrita, tarefas idempotentes e validação de recibos.
- [x] Implementar guard para etapas e conclusão interna sem mensagem externa.
- [x] Atualizar conduta CEO/Reno, workflow, instruções de operação e rollback.
- [x] Rodar testes, replay e verificar instalação oficial intacta.
- [x] Instalar extensão Reno e timer operacional; confirmar ativação sem testar
      com clientes reais. Registrar limites e resultados.
