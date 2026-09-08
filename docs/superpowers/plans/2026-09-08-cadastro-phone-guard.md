# Cadastro: comparação determinística e handoff verificado

**Goal:** impedir a confusão observada entre candidatos por sufixo e telefones completos correspondentes. Aprovação: conversa de 2026-09-08, recomendação aceita com “ok”.
**Architecture:** plugin externo exclusivo dos workers Cadastro, sem alteração do core Hermes ou do Brain. Observa respostas reais de ferramentas; valida antes do POST; produz summary e metadata canônicos antes de kanban_complete. Estado em memória por worker/sessão, sem PII persistida pelo plugin. Mantém as três APIs FamaChat existentes.
**Tech:** Python stdlib e PyYAML já incluído no Hermes, hooks nativos pre_tool_call/post_tool_call/transform_tool_result, unittest; configuração via CLI Hermes.

- [x] Inspecionar contrato real dos hooks, respostas MCP e isolamento por worker.
- [x] Baseline: 18 testes operacionais existentes passam.
- [x] RED: reproduzir quatro candidatos com mesmo sufixo e zero telefones equivalentes; demais limites de identidade, paginação, criação e readback.
- [x] GREEN: comparador e guard integrado; falhas internas bloqueiam operações dependentes; decisão e contagens saem da mesma evidência.
- [x] Alinhar SOUL e skill como referência das novas chamadas e respostas; manter limites de negócio, modo sintético e ausência de atendimento externo.
- [x] Revisão independente de código e aplicação das instruções a cenários sintéticos.
- [x] Validar integração usando dispatcher Hermes real e replay local de ferramentas históricas, sem chamadas de escrita externas.
- [ ] Integrar e ativar apenas para próximos workers Cadastro; conferir plugin/configuração e registrar evidência sem PII.

Critérios: país/pontuação/nono dígito permitidos; DDD e demais dígitos precisam coincidir. Um cliente Reno não arquivado impede criação; múltiplos clientes Reno exigem conferência. Busca incompleta/erro nunca prova ausência. Um POST por execução; readback exige ID, telefone, broker35 e Sem Atendimento. Handoff não depende de contagens fornecidas pelo modelo. Consulta de página cheia precisa prosseguir até página curta; pagination.total não é total da base. Sem evidência, saída INCONCLUSIVO. Não se promete impedir concorrência entre workers distintos nem falhas no carregamento de plugins do core; validar carregamento e documentar esses limites.
