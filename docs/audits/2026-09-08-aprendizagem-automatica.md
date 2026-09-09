# Aprendizagem automática dos profiles Hermes

Verificação concluída em 2026-09-08T21:18:16.102411-03:00, BRT. Escopo: CEO/default, Cadastro, Dev,
FamaAgent, Porteiro e Reno.

## Resultado

Memória, criação/atualização de skills e revisão automática estão habilitadas
nos seis profiles, sem aprovação individual de gravação. Os testes usaram as
ferramentas nativas, stores reais e modelos configurados; não houve envio de
mensagens nem chamada comercial durante os ensaios.

| Profile | Gravar e recuperar memória/skill em outro processo | Revisão automática real | Resultado observado |
|---|---|---|---|
| CEO/default | Passou | Concluiu | `result=none`: nenhuma nova gravação necessária |
| Cadastro | Passou | Concluiu | Memória e skill atualizadas |
| Dev | Passou | Concluiu | Referência de skill atualizada |
| FamaAgent | Passou | Concluiu | Memória e skill atualizadas |
| Porteiro | Passou | Concluiu | Memória atualizada; nova skill e referência criadas |
| Reno | Passou | Concluiu | Referência de skill atualizada |

As cinco skills criadas/atualizadas pelo revisor foram carregadas em processos
independentes. As entradas temporárias dos testes nativos foram removidas.
Os ensaios com modelo deixaram apenas o aprendizado técnico efetivamente salvo;
a revisão independente não encontrou propagação de marcadores de teste ou
alteração de regras comerciais nas skills aprendidas.

## Ajustes aplicados

- `memory.memory_enabled` e `memory.user_profile_enabled`: `true`.
- `memory.write_approval` e `skills.write_approval`: `false`.
- `auxiliary.background_review.enabled`: `true` explicitamente.
- `memory.nudge_interval: 1` e `skills.creation_nudge_interval: 1`, para também
  alcançar tarefas curtas. O primeiro conta turnos de usuário; o segundo,
  iterações de ferramentas. Isso aumenta a frequência/custo de revisões frente
  ao intervalo anterior de 10; os modelos foram preservados.
- `skills.ledger: true`; guardas de conteúdo mantidas.
- Ferramentas de aprendizagem disponíveis nos canais configurados, respeitando
  a resolução nativa de composites. Não houve remoção de ferramentas anteriores
  nem acréscimo de capacidades comerciais.
- Autorização permanente em cada `SOUL.md`, inclusive para workers e revisão
  em segundo plano. Corrigida a instrução obsoleta de memória desabilitada no
  Cadastro e no Porteiro.

## Correção do encerramento do worker

O CLI one-shot encerrava a thread daemon `bg-review` sem aguardar sua conclusão.
Um subprocesso com gravação atrasada reproduziu a perda antes da mudança.

O plugin local [fama-learning-lifecycle](../../ops/plugins/fama-learning-lifecycle/__init__.py)
usa `on_session_finalize` para aguardar a revisão no encerramento do CLI,
com limite padrão fixo de 300 segundos. Cada home tem o plugin instalado por
link para a fonte operacional. O teste pelo finalizador oficial passou após
instalar o plugin; duas verificações focadas cobrem registro do hook,
conclusão da gravação, isolamento dos canais gateway e limite de espera.

A revisão dos gateways permanece assíncrona. Ao atingir o limite de espera,
o plugin registra revisões pendentes; isso não deve ser reportado como gravação
concluída. A revisão nativa também pode ser cancelada por um novo turno ou
concluir sem aprendizado novo.

## Ativação em execução

Os snapshots anteriores de instruções/ferramentas foram guardados em backup
privado e invalidados pelas APIs nativas, preservando mensagens e sessões:
64 no CEO, 3 no Cadastro, 5 no Dev, 3 no FamaAgent, 3 no Porteiro e 2 no Reno.

Os seis gateways foram reiniciados pelo fluxo nativo de espera dos turnos,
sem reinício forçado. A verificação final confirmou novos PIDs, estado `running`,
Telegram conectado em todos e WhatsApp conectado no CEO. Nenhuma sessão ativa
selecionada mantinha o snapshot antigo ao final da conferência.

## Limites e verificações adicionais

- Os ensaios reais são administrativos controlados, com contadores naturais e
  sem forçar o disparo da revisão. Não equivalem a testar todos os atendimentos
  comerciais possíveis.
- Filhos de `delegate_task` têm bloqueio nativo da ferramenta `memory`.
  A política do Dev orienta o agente pai a consolidar as lições dos filhos.
  Não foi liberada escrita direta de memória nesses filhos; a instalação do
  Hermes permaneceu sem alteração.
- `hermes config check`: passou nos seis profiles. Testes do plugin: 2 passaram.
  Revisão independente concluída; `git diff --check` sem erros.
- O verificador legado `verify_team.py core` ainda acusa 13 divergências de
  contratos/configurações anteriores. Executado contra o backup anterior e o
  estado final, retornou as mesmas 13 divergências: nenhuma nova. Incluem
  expectativas antigas de toolsets e MCPs; não se declarou a frota inteira
  aprovada por esse verificador nem se ampliou o escopo para corrigi-las.
- Arquivo `ops/hermes-team/PENDENCIAS-SEGURANCA.md` apareceu de trabalho
  concorrente e não foi alterado por esta tarefa.

## Artefatos e reprodução

- [Evidência estruturada](2026-09-08-learning-evidence.json).
- [Verificador de aprendizagem](../../ops/hermes-team/verify_learning.py).
- [Testes do ciclo de vida](../../ops/hermes-team/tests/test_learning_lifecycle.py).
- [Runbook](../../ops/hermes-team/RUNBOOK.md).
- Backup privado de configurações/instruções e snapshots:
  `/root/.hermes/cache/learning-backup-20260909T000638Z/`.

As configurações e fontes estão aplicadas localmente. Nenhum push ou publicação
foi realizado.
