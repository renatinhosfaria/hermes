# Arquitetura vigente — Equipe multiagente Hermes da Fama

Data: 2026-09-01 (revisado no mesmo dia, após a adoção do Hermes 0.21.0)  
Status: as built, verificado no VPS  
Substitui como contrato vigente: `2026-08-24-hermes-equipe-multiagente-design.md`

## 1. Objetivo

Registrar a arquitetura que está efetivamente implantada no VPS após a fase
inicial de 24/08 e as evoluções posteriores, incluindo gateways individuais,
canais internos no Telegram, integração Brain/FamaChat, isolamento de
ferramentas e as regras do Amendment 2.

Este documento descreve o estado operacional. Configurações dos Profiles,
units systemd, `ops/hermes-team/verify_team.py` e o histórico Git continuam
sendo as fontes técnicas executáveis.

## 2. Escopo desta consolidação

Esta revisão:

- documenta a topologia vigente sem alterá-la;
- atualiza o runbook operacional;
- preserva os documentos de 24/08 como registro histórico da primeira fase;
- não muda Profiles, prompts, skills, modelos, gateways ou integrações;
- não reinicia serviços;
- não lê, copia ou modifica credenciais;
- não altera cartões Kanban.

## 3. Evolução desde 24/08

O desenho original estabeleceu seis Profiles, um único gateway, Kanban Manual
e nenhuma integração MCP. Essa implantação foi concluída, mas deixou de ser a
topologia vigente.

As mudanças posteriores introduziram:

- gateway e home channel Telegram próprios para cada Profile;
- dispatcher Kanban ainda exclusivo do `default`/CEO;
- Brain como fonte autorizada de identidade e histórico de conversa;
- FamaChat com allowlists mínimas e específicas por worker;
- exposição de MCP isolada por plataforma;
- CEO e Dev promovidos para o modelo Sol;
- novas regras de idempotência e transição de etapa pelo Amendment 2;
- Git e `verify_team.py` como controles de drift, substituindo um manifesto de
  checksums que não era verificável.

Consequentemente, afirmações antigas como “gateway único”, “Dev sem gateway” e
“FamaChat não configurado” são históricas, não critérios atuais de aceite.

### 3.1 Adoção do Hermes 0.21.0 (2026-09-01)

A atualização para 0.21.0 já estava aplicada quando esta revisão começou; os
seis gateways foram confirmados em `18a76be1` e `_config_version` permaneceu em
39, sem migração pendente. O §15 desta especificação exige desenho próprio para
qualquer evolução, e esta subseção registra o resultado dele.

Entrou:

- resiliência do dispatcher Kanban, com cinco chaves antes ausentes (§10);
- guarda de escrita em arquivos de instrução, com o Dev como exceção (§11.1);
- `mcp.auto_reload_on_config_change: false` nos quatro Profiles com MCP, para
  não invalidar o prompt cache a cada mudança de configuração;
- delegação interna no Dev, com filho em modelo leve (§5.1);
- verificação automática da frota por cron em modo monitor (§14.1);
- `scripts/` e `profiles/*/scripts/` versionados, exigência do cron.

Avaliado e recusado, com a razão registrada porque o valor está em impedir que
a ideia volte:

- **`model_overrides` no lugar de `model.context_length`** — são camadas
  distintas da cadeia de resolução, não sinônimos.
- **`delegate_task` nos Profiles de negócio** — o filho herda o toolset do pai
  sem herdar o SOUL, e ferramentas MCP não constam de `DELEGATE_BLOCKED_TOOLS`.
  Um filho do Reno teria `fc_patch_clientes_by_id` sem a disciplina de
  `expectedStatus`; um do Cadastro teria `fc_post_clientes` sem o “no máximo uma
  vez”.
- **Bot Mode, `message_agent` e `hermes peer`** — dariam DM direto entre
  especialistas, contra o §8.1. `verify_team.py` passou a afirmar a contenção
  em vez de depender de ela nunca ter sido ligada por acaso.
- **`hooks.outbound` para alarme de cartão bloqueado** — a premissa não
  sobreviveu: `kanban_notify_subs` mostra `last_event_id` igual ao id do evento
  `blocked` nos três cartões, ou seja, `auto_subscribe_on_create` já notifica. O
  que faltava era visão agregada para o operador, entregue pelo cron do §14.1.
  `hooks.outbound` segue reservado para alimentar o Brain sem polling.

## 4. Topologia vigente

```text
WhatsApp externo
      │
      ▼
hermes-gateway.service ── default / CEO ── dispatcher Kanban
      ▲                                      │
      │                                      ├─ porteiro
Telegram do operador                         ├─ cadastro
      │                                      ├─ famaagent
      ├─ canal CEO                           ├─ reno
      ├─ canal Porteiro                      └─ dev
      ├─ canal Cadastro
      ├─ canal FamaAgent        gateways internos próprios
      ├─ canal Reno             (Telegram/CLI, sem dispatcher)
      └─ canal Dev
```

Existem seis gateways systemd, todos `active/enabled`:

| Profile | Unit | Papel do gateway | Dispatcher Kanban |
|---|---|---|---|
| `default` / CEO | `hermes-gateway.service` | Telegram do CEO, WhatsApp externo e orquestração | habilitado |
| `porteiro` | `hermes-gateway-porteiro.service` | canal interno dedicado | desabilitado |
| `cadastro` | `hermes-gateway-cadastro.service` | canal interno dedicado | desabilitado |
| `famaagent` | `hermes-gateway-famaagent.service` | canal interno dedicado | desabilitado |
| `reno` | `hermes-gateway-reno.service` | canal interno dedicado | desabilitado |
| `dev` | `hermes-gateway-dev.service` | canal interno dedicado | desabilitado |

Cada Profile tem home channel Telegram exclusivo. Todos restringem o operador
pela mesma allowlist; os especialistas também limitam grupos ao próprio home
channel. Ter um gateway próprio não autoriza um especialista a responder no
WhatsApp nem a assumir a orquestração.

## 5. Profiles, modelos e responsabilidades

| Profile | Modelo | Esforço | Responsabilidade |
|---|---|---|---|
| `default` / CEO | `gpt-5.6-sol-900k` | `high` | receber canais externos, obter contexto, criar cartões, validar handoffs e enviar respostas |
| `porteiro` | `gpt-5.6-luna-900k` | `xhigh` | provar identidade e determinar se o contato é corretor ativo |
| `cadastro` | `gpt-5.6-luna-900k` | `xhigh` | localizar cliente ou criar lead de forma controlada |
| `famaagent` | `gpt-5.6-luna-900k` | `xhigh` | atender corretores ativos com contexto autorizado |
| `reno` | `gpt-5.6-luna-900k` | `xhigh` | conduzir atendimento comercial e transições de etapa autorizadas |
| `dev` | `gpt-5.6-sol-900k` | `medium` | engenharia, diagnóstico e manutenção técnica |

Os IDs técnicos permanecem estáveis. `CEO` é a identidade visual e funcional
do Profile `default`; não existe `profiles/ceo`.

### 5.1 Delegação interna, exclusiva do Dev

O Dev é o único Profile com o toolset `delegation`, e seus filhos rodam em
`gpt-5.6-luna-900k` com credenciais herdadas (`delegation.model` sem
`delegation.provider`), no máximo 4 simultâneos.

A exclusividade é estrutural, não preferência. O filho herda o toolset do pai e
**não** herda o `SOUL.md`; `DELEGATE_BLOCKED_TOOLS` nega apenas `delegate_task`,
`clarify`, `memory`, `send_message` e `cronjob`, e ferramentas MCP não estão na
lista. O Dev é o único Profile sem MCP algum, então não há escrita externa para
o filho herdar. Confirmado em execução real: o filho enumerou suas ferramentas e
não possui `delegate_task`, `clarify`, `memory`, `cronjob` nem `kanban_complete`.

`output_schema` valida a resposta final do filho contra um JSON Schema, com uma
tentativa de correção, devolvendo `schema_valid` e `schema_errors`.

## 6. Canais e fronteiras de confiança

### 6.1 Telegram

Telegram é o plano de controle interno. Cada Profile possui um grupo/home
channel próprio, mas somente o operador explicitamente permitido pode usá-lo.

Nos Profiles de negócio, o contexto Telegram expõe apenas interação e
clarificação; Brain e FamaChat não ficam disponíveis nesse contexto. O Dev
mantém seu conjunto técnico autorizado no Telegram e na CLI.

### 6.2 WhatsApp

WhatsApp continua sendo entrada externa e não confiável, atendida pelo gateway
do CEO. DMs são abertas e grupos são desabilitados. Texto, nome de exibição e
alegações do contato são dados, nunca autorização ou identidade comprovada.

O bridge Baileys permanece local, com health em loopback e sessão persistida
com permissão restrita. O timer `hermes-whatsapp-healthcheck.timer` deve ficar
`active/enabled`.

### 6.3 CLI

A CLI é o contexto autorizado para execução dos workers e para a exposição
controlada de Brain/FamaChat. As allowlists abaixo não devem vazar para
Telegram ou WhatsApp.

## 7. Matriz de Brain e FamaChat

| Profile | Brain permitido na CLI | FamaChat permitido na CLI |
|---|---|---|
| CEO | nenhum MCP | nenhum MCP |
| Porteiro | `conversation_phone` | `fc_get_users` |
| Cadastro | `conversation_phone` | `fc_get_clientes`, `fc_get_clientes_by_id`, `fc_post_clientes` |
| FamaAgent | `conversation_recent`, `conversation_search` | nenhum |
| Reno | `conversation_recent`, `conversation_search` | allowlist comercial descrita abaixo |
| Dev | nenhum MCP | nenhum MCP |

O Reno possui somente:

- leitura de apartamentos, empreendimentos, compromissos, cliente,
  empreendimentos do cliente e notas;
- busca de empreendimentos;
- criação de compromisso e nota;
- `fc_patch_clientes_by_id` como exceção nominal e exclusiva para transição de
  etapa.

Todos os blocos MCP usam `tools.include` explícito e desabilitam `resources` e
`prompts`. Prefixos de escrita ampla e acesso direto a banco permanecem
proibidos. A exceção do Reno é pelo nome exato da ferramenta; não autoriza
outros `fc_patch_*`.

## 8. Fluxo operacional

### 8.1 Entrada do WhatsApp

1. O CEO obtém o contexto autorizado da conversa com
   `conversation_context()`.
2. Nome de exibição é propagado apenas como dado não confiável.
3. O CEO cria o cartão mínimo para o Porteiro.
4. O Porteiro resolve o telefone pela própria capability Brain e consulta o
   usuário no FamaChat.
5. Corretor ativo segue para o FamaAgent.
6. Contato não corretor segue para o Cadastro.
7. Cliente existente ou lead criado segue para o Reno.
8. O CEO valida correlação, vigência e `response_ready` antes de responder no
   WhatsApp.

Especialistas não enviam a resposta externa e não delegam diretamente uns aos
outros. Nova necessidade retorna ao CEO.

### 8.2 Falha do Brain

Indisponibilidade do Brain não silencia o contato. O CEO cria o cartão mínimo
com `context_resolution_failed: true`; o worker tenta sua capability
autorizada. Sem identidade comprovada, a ramificação bloqueia de forma
estruturada. Não se pede telefone ao contato como substituto automático e não
se inventa identificador técnico.

### 8.3 Idempotência vigente

O contrato antigo baseado em `wa_turn_id` foi removido. Esse campo não existe
mais e nenhum reconciliador consome chaves no formato antigo.

O Kanban fornece sua própria idempotência. Quando não houver identificador
técnico verdadeiro, o CEO omite `idempotency_key`; jamais compõe uma chave a
partir de telefone, nome, mensagem ou UUID improvisado.

## 9. Regras de escrita no FamaChat

### 9.1 Cadastro

- `fc_post_clientes` é chamado no máximo uma vez por criação.
- O retorno do POST não prova o estado persistido.
- O Cadastro relê o registro por ID com `fc_get_clientes_by_id`.
- O readback deve confirmar conjuntamente identidade, broker e etapa inicial
  esperada antes do handoff.

### 9.2 Reno

- Toda transição usa `expectedStatus` obtido por leitura imediatamente
  anterior.
- Um conflito `409` não é contornado por nova escrita forçada.
- Só são permitidas transições progressivas:

```text
Sem Atendimento  →  Não Respondeu
Sem Atendimento  →  Em Atendimento
Não Respondeu    →  Em Atendimento
```

- O Reno nunca retrocede a etapa, mesmo quando `expectedStatus` confere.
- Histórico recente é lido uma vez, exatamente no primeiro cartão aplicável;
  indisponibilidade do Brain é registrada sem bloquear automaticamente o
  atendimento.

## 10. Kanban e handoffs

O `default` é o único orquestrador e o único gateway com
`dispatch_in_gateway: true`. Nos outros cinco Profiles esse campo é
explicitamente `false`. `auto_decompose` permanece desabilitado.

Cinco chaves de resiliência, ausentes até 2026-09-01 e por isso operando em
default:

| Chave | Valor | Por quê |
|---|---|---|
| `dispatch_stale_timeout_seconds` | 3600 | O default de 14400 deixava cartão travado quatro horas antes de voltar a `ready`. 3600 é quatro vezes mais rápido sem descer abaixo de `DEFAULT_CLAIM_HEARTBEAT_MAX_STALE_SECONDS`, que é a definição do próprio Hermes de worker travado — um valor menor reclamaria worker que o framework ainda considera vivo |
| `default_assignee` | `dev` | Sem isso, cartão com assignee não reconhecido cai no `default`, que por contrato não executa. O board tinha `t_e1c6c719` com assignee `pingpong` como precedente |
| `max_in_progress_per_profile` | 2 | Um Profile podia ocupar os quatro slots globais e travar os outros |
| `worker_log_rotate_bytes` | 8388608 | O default de 2 MiB descartava evidência de falha rápido demais |
| `worker_log_backup_count` | 3 | idem |

Cartões devem ser autossuficientes, minimizar PII e separar:

- `body`: somente contexto indispensável ao trabalho;
- `summary`: conclusão curta sem telefone ou mensagem bruta;
- `metadata`: decisão, IDs internos necessários, evidência e próxima ação;
- `response_ready`: somente texto candidato a entrega externa.

Uma notificação ou summary truncado nunca substitui a leitura do handoff
durável. Resultados atrasados permanecem auditáveis, mas não são enviados sem
validação do CEO.

## 11. Segurança e dados

- Segredos ficam fora de prompts, cartões, summaries, metadata e Git.
- Telefone aparece apenas no limite operacional que realmente precisa dele.
- MCPs são negados por padrão e liberados por Profile, plataforma e nome exato
  de ferramenta.
- WhatsApp nunca autoriza manutenção, leitura de segredos ou alteração da
  equipe.
- Display name não é identidade.
- Workers não usam terminal, SQLite ou busca de sessão como atalho para Brain
  ou FamaChat.
- Toda mudança de contrato deve atualizar `verify_team.py` no mesmo commit.

### 11.1 Guarda de arquivos de instrução

`security.protected_instruction_files` está fixado explicitamente em vez de
depender do default do 0.21.0, e `protected_instruction_extra_patterns` estende
a proteção a `SKILL.md`, `profile.yaml`, `config.yaml` e `.hermes.md`.

**Escopo real, verificado em execução e não deduzido.** A guarda entrega
isolamento *entre* Profiles: nenhum Profile de negócio escreve `SOUL.md`,
`config.yaml`, `SKILL.md` ou `profile.yaml` de outro. Ela **não** impede um
Profile de reescrever a própria instrução — `tools/file_tools.py:812` isenta
explicitamente tudo sob o `HERMES_HOME` ativo, porque foi desenhada para
arquivos de projeto, não para a casa do Hermes.

O **Dev é exceção deliberada**, com `protected_instruction_files: false`: seu
charter é manter profiles, configurações, instruções e skills de todos os
Profiles, e a guarda ligada impedia exatamente isso.

Duas limitações que permanecem:

- a guarda vive em `write_file`/`patch`; `terminal` não passa por ela;
- nem o Dev escreve o próprio `config.yaml` por `write_file` —
  `tools/file_tools.py:706` recusa o config do `HERMES_HOME` ativo sem chave de
  configuração. A saída é `terminal` ou `hermes config`.

## 12. Operação, falhas e cartões bloqueados

No snapshot de 2026-09-01, o Kanban não tinha diagnóstico crítico, com 82
cartões concluídos, 17 arquivados e **três** bloqueados:

- `t_67fd1a55`, Porteiro, `block_kind: needs_input`;
- `t_3037b094`, Cadastro, `block_kind: capability`;
- `t_dea78e0d`, Dev, `block_kind: capability`.

Os três **foram notificados**: em `kanban_notify_subs`, o `last_event_id` de
cada um é exatamente o id do seu evento `blocked` (459, 690 e 767). O
`auto_subscribe_on_create` funciona. A notificação vai para a conversa de
origem, que em cartão de lead é a DM do próprio lead — acorda o CEO ali dentro
em vez de avisar o operador. É essa lacuna, e não ausência de sinal, que o cron
do §14.1 cobre.

Esses cartões são estado operacional preexistente, não falha desta
consolidação. Devem ser triados pelo conteúdo e histórico do cartão antes de
qualquer retry, reatribuição ou cancelamento. A documentação não os modifica.

Falhas de gateway são tratadas por unit. Falha de WhatsApp é tratada no gateway
do CEO e no healthcheck Baileys; falha de um worker não justifica reiniciar os
demais gateways.

## 13. Fontes de verdade e controle de drift

Ordem prática de verificação:

1. estado vivo de systemd, gateway, WhatsApp e Kanban;
2. `config.yaml`, `SOUL.md`, skills e metadata de cada Profile;
3. `ops/hermes-team/verify_team.py`, que codifica invariantes e allowlists;
4. histórico Git, com worktree limpo e HEAD conhecido;
5. esta especificação e o runbook como explicação humana do contrato.

Não existe manifesto `DEPLOYED_SHA256SUMS`: o anterior misturava arquivos
voláteis, continha entradas impossíveis de validar e não era executado. Git
registra integridade de arquivos versionados; o verificador testa o conteúdo
operacional relevante.

## 14. Verificação de aceite

Esta consolidação é aceita quando:

- `verify_team.py full` retorna PASS;
- seis gateways e o timer WhatsApp estão `active/enabled`;
- health do Baileys retorna `connected` em loopback;
- `hermes kanban diagnostics --json` retorna lista vazia;
- a matriz MCP resolvida por plataforma coincide com o verificador;
- o Git contém somente as mudanças documentais esperadas antes do commit;
- nenhuma configuração, credencial, unit ou cartão foi alterado.

## 15. Próximas mudanças

Qualquer evolução funcional — novo Profile, nova ferramenta MCP, mudança de
modelo, política de canal, alteração de handoff ou atualização do Hermes — deve
ter desenho e plano próprios.

A adoção do 0.21.0 seguiu essa regra e está registrada no §3.1.

Nenhuma frente do plano de adoção do 0.21.0 permanece aberta.

### 15.1 Frentes fechadas em 2026-09-01, sem adoção

**`hooks.outbound` para o Brain — não adotar.** Esta especificação chegou a
registrar a frente como aberta, com a justificativa de dar ao Brain o ciclo de
vida do cartão "sem polling". A verificação desmentiu a premissa: **não existe
polling a eliminar.**

O Brain lê `kanban.db`, mas não para acompanhar andamento. Lê para **autorizar**,
de forma síncrona, a cada chamada MCP de worker (`src/brain/authorization.py`,
`authorize_worker`): confere que a tarefa existe, que está `running`, que o
`current_run_id` bate com o run apresentado, que o `assignee` é o principal que
está chamando, e que existe exatamente uma inscrição WhatsApp de tipo `dm`
ligando a tarefa a um único `chat_id`. Só então entrega o histórico do contato.

Um webhook não substitui isso, e o motivo é categórico: webhook informa um
evento passado, e uma decisão de autorização precisa do estado autoritativo no
instante da chamada. Trocar a leitura síncrona por uma cópia de eventos
recebidos faria o Brain decidir liberação de dado de cliente sobre estado
possivelmente defasado — o mecanismo fraco no lugar do forte.

Some-se a isso o Amendment 2 (2026-08-31), que **removeu de propósito** do Brain
a derivação de estado a partir do Kanban: ele não correlaciona mais turnos do
Hermes nem reconstrói vínculos, e o Reno passou a executar as transições pela
própria superfície MCP. Alimentar o Brain com esses eventos empurraria o serviço
de volta ao escopo que a emenda retirou.

**`kanban swarm` — não adotar.** A topologia raiz → workers paralelos →
verificador → sintetizador não encontra trabalho nesta arquitetura:

- o fluxo de lead é cadeia sequencial com dependência de dados — Porteiro prova
  identidade, e só então Cadastro classifica, e só então Reno atende. Não há
  workers paralelos para paralelizar;
- o único leque plausível era o Dev auditando Profiles. Os seis cartões
  históricos desse tipo falharam com `pid … exited with code 1` — crash de
  processo worker, falha de infraestrutura que o swarm não corrige; a leva
  seguinte, idêntica em forma, passou sem falha;
- esse nicho passou a ser coberto por `delegate_task` com `output_schema`
  (§5.1): valida a saída de cada filho contra schema, roda em modelo mais leve
  e não gera cartões;
- a metade restante — o verificador — acrescentaria uma rodada de agente **no
  caminho do lead**, ou seja, latência e custo exatamente onde vale a regra
  inegociável de não deixar ninguém esperando, para auditar algo que já
  funciona.

**Curadoria de `fama-ceo-runtime` — manter fora da curadoria.** A skill consta
entre as 14 não gerenciadas em `hermes curator status`, o que significa que
nunca é marcada obsoleta, nunca é arquivada automaticamente e nunca é reescrita
pelo fork de background review. Para o contrato operacional do CEO — verificado
marcador a marcador pelo `verify_team.py` e governado pela regra de mudança
autorizada — esse é o estado desejado. `hermes curator adopt` faria o oposto.

O aviso recorrente em `logs/errors.log` (*"Refusing background curator patch …
the skill is not curator-managed"*) é a proteção relatando que funcionou, não um
defeito. Desligar `auxiliary.background_review` no `default` pararia as
tentativas, mas removeria uma capacidade que o `SOUL.md` do CEO autoriza
explicitamente, e não existe exclusão por skill na configuração.
