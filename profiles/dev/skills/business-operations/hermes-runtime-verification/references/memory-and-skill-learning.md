# Verificar memória e aprendizado por skills

## Camadas e critérios

- Separe configuração persistida, ferramentas da conversa atual, carregamento em
  processo novo e execução real da revisão automática. Um teste de leitura não
  comprova que o modelo criou uma skill em segundo plano.
- Consulte a documentação oficial de `features/memory` e `features/skills`, e
  confira os consumidores na versão instalada antes de interpretar defaults.
- Verifique `memory.memory_enabled`, `memory.write_approval`,
  `memory.nudge_interval`, `skills.write_approval`,
  `skills.creation_nudge_interval`, `skills.guard_agent_created` e
  `auxiliary.background_review.enabled` com `hermes -p <alvo> config get`.
- Confirme `memory`, `skills` e `session_search` na plataforma alvo. USER.md é
  opcional: `user_profile_enabled: false` não impede MEMORY.md nem aprendizado
  procedural. Não habilite outro armazenamento ou provedor externo sem necessidade.

## Semântica dos gatilhos

- Na versão inspecionada, `agent/agent_init.py::_apply_agent_section` lê
  `skills.creation_nudge_interval` com padrão 10. O CLI pode avisar que a chave
  não é reconhecida pelo catálogo mesmo quando o runtime a consome: teste o
  consumidor real antes de concluir que a configuração não funciona.
- `agent/turn_iteration_prep.py` conta iterações de ferramenta; o finalizador
  verifica o limiar de skills ao terminar a resposta. O intervalo de memória
  conta turnos do usuário, não minutos. Zero desabilita o respectivo gatilho.
- `agent/background_review.py::load_background_review_settings` resolve o gate
  global. A revisão depende também de ferramentas disponíveis, término não
  interrompido e ausência de `skip_background_review`.
- Revisão pode concluir sem alterações; `result=none` nos logs não é prova de
  criação ou persistência de uma skill. Não prometa uma nova skill por conversa.
- Curator mantém o ciclo de vida da biblioteca; não é o interruptor do
  aprendizado. Não ative consolidação nem altere arquivamento para habilitar
  criação. Confira a versão: `curator.prune_builtins` pode permitir arquivar
  skills empacotadas, portanto não assuma que todas elas estão excluídas.

## Prova prática sem conteúdo artificial

1. Grave um fato realmente durável com `memory`, ou refine um fato existente.
2. Em outro processo Python, com o home do profile correto e bytecode desabilitado,
   use `tools.memory_tool.load_on_disk_store()` e
   `format_for_system_prompt('memory')`; faça uma asserção sem imprimir notas.
3. Registre um aprendizado comprovado com `skill_manage`: prefira estender uma
   skill existente; criar conteúdo fictício apenas para teste polui a biblioteca.
4. Carregue a skill/referência gravada pela função nativa `skill_view` em processo
   independente; confirme sucesso e conteúdo esperado. Isso comprova persistência
   e recuperação, não uma decisão autônoma futura do modelo.
5. Execute `config check`, examine o diff e a integridade da instalação. Commite
   somente os arquivos da tarefa, respeitando exclusões de memória privada.
6. Relate separadamente: escrita/recarga testadas agora; evidência histórica de
   revisões; e qualquer execução de ponta a ponta ainda não observada.

## Verificador do Dev

Execute com o Python do Hermes e `HERMES_HOME` explícito:

```text
HERMES_HOME=/root/.hermes/profiles/dev PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python3 -B /root/.hermes/profiles/dev/scripts/verify_learning.py
```

Sem argumentos, verifica configuração e recuperação nativa de memória/skill.
Com `--live`, faz inferência real e aguarda o fork pós-turno com contadores
preparados no limiar; há custo de modelo e valem as permissões normais de
aprendizado. O probe não reinicia gateway nem altera seus contadores. Revalide
APIs privadas do script depois de um update do Hermes.

## Guardas e prova de execução

- Confira `tools/skill_manager_guards.py` antes de diagnosticar uma falha de
  aprendizado: a revisão não altera skills fixadas, empacotadas, externas,
  instaladas pelo hub ou sem proveniência de gestão pelo agente. Escrita livre
  (`skills.write_approval: false`) não remove essas proteções. Não adote skills
  nem altere sua proveniência apenas para fazer um teste passar.
- Distinga o lembrete automático do teste controlado: preparar o contador no
  limiar em um agente temporário testa o finalizador com uma chamada real ao
  modelo, mas não demonstra que o limiar foi atingido naturalmente na conversa
  de produção. Preserve configuração, intervalos e permissões do profile.
- Aguarde a conclusão do fork no processo de teste; a thread é daemon e pode
  ser encerrada ao sair um CLI de uma única pergunta. Use o registro nativo
  `Background review complete` como evidência, separando `result=none` de
  escrita bem-sucedida e de erro. Não confunda criação do cliente com conclusão.
- Notas de memória gravadas durante uma sessão entram no disco imediatamente,
  mas o snapshot do prompt fica congelado; valide recuperação em processo novo,
  não pela permanência do texto antigo no prompt atual.

Não amplie o whitelist de ferramentas do background review para conseguir Git.
O fork nativo admite memória, skills e leitura, mas normalmente não terminal.
Não contorne recusas nem faça commit de alterações cuja origem não foi auditada.
