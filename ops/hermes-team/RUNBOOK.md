# Runbook — Equipe Hermes da Fama

## Estado esperado

- Gateways ativos e habilitados: `hermes-gateway.service` e os gateways
  `porteiro`, `cadastro`, `famaagent`, `reno`, `agendamento` e `dev`.
- Profiles: `default`, `porteiro`, `cadastro`, `famaagent`, `reno`,
  `agendamento`, `dev`.
- Modelos: CEO, Reno, Agendamento e Dev em `gpt-6-astra-900k`; Porteiro,
  Cadastro e FamaAgent em `gpt-5.6-luna-900k`. O Agendamento deve usar
  exatamente a configuração de modelo vigente do Reno.
- Kanban: dispatcher somente no gateway do CEO; `dispatch_in_gateway: false`
  nos seis especialistas; decomposição automática desligada.
- Telegram: somente Renato pela allowlist, com home channel exclusivo por
  Profile ativo. O Agendamento usa o bot `@agendamentofama_bot`, destino
  `-1003944432295`, sem tópico. `telegram.allowed_chats` contém somente esse
  destino, `telegram.group_allowed_chats` permanece vazio e
  `telegram.allow_from` contém somente o operador `8564576789`; o grupo não
  concede autorização a todos os seus participantes.
- WhatsApp: modo bot, DMs abertas, grupos desabilitados.
- Alerta de WhatsApp: `hermes-whatsapp-healthcheck.timer` ativo; alerta após
  três falhas consecutivas e mensagem de recuperação quando o health volta.
- MCPs: Brain/FamaChat somente nos Profiles e contextos permitidos por
  `verify_team.py`; não são expostos nos canais Telegram dos workers.
  Agendamento expõe no CLI somente FamaChat e as cinco ferramentas
  `fc_get_clientes_by_id`, `fc_get_appointments`,
  `fc_get_appointments_by_id`, `fc_post_appointments` e
  `fc_patch_appointments_by_id`. Reno não expõe as duas ferramentas de agenda
  que foram transferidas (`fc_get_appointments_by_id` e
  `fc_post_appointments`).
- Delegação: somente o Dev tem o toolset `delegation`; filhos em
  `gpt-5.6-luna-900k`, no máximo 4 simultâneos.
- Manutenção pelo Telegram: todos os Profiles têm terminal, edição de arquivos
  e skills para executar pedidos explícitos do operador sobre o próprio Profile.
- Guarda de instrução: `protected_instruction_files: false` e
  `skills.write_approval: false` nos seis Profiles, por decisão do operador em
  07/09. As demais aprovações do runtime continuam vigentes.

## Manutenção pelo bot Telegram — 07/09/2026

O operador pode pedir ao bot de qualquer Profile que altere sua configuração,
instruções, comportamento ou skills. A identidade deve vir dos metadados do
Telegram e corresponder a `telegram.allow_from`. O Profile executa e responde
diretamente; não exige atendimento em andamento nem encaminha ao Dev. Para a
manutenção própria, o CEO também está dispensado de delegação e cartão Kanban.

Para runtime, use `hermes -p <profile> config set <chave> <valor>` e confira com
`config get` e `config check`; no CEO, use `hermes -p default config`. O bloqueio do core
contra escrever o próprio `config.yaml` com `write_file`/`patch` permanece.
Instruções e outros arquivos textuais podem ser editados com `patch`/`write_file`.
Recusas ou aprovações das ferramentas continuam sendo respeitadas.

Nos Profiles especialistas, somente `platform_toolsets.telegram` ganhou
`terminal`, `file` e `skills`. MCPs, capacidades de atendimento do CLI e do
WhatsApp, allowlists e credenciais foram preservados. O Dev mantém seu escopo
de manutenção dos demais Profiles quando o alvo estiver declarado na tarefa.
Credenciais, bancos de estado, sessões de plataforma e instalação do Hermes
não fazem parte da manutenção própria autorizada.

Instruções já montadas ficam em cache por conversa e podem sobreviver ao
reinício do gateway. Para aplicar uma mudança às conversas existentes em uma
manutenção planejada, renove somente o snapshot de instruções das sessões
Telegram selecionadas com a API `SessionDB.update_system_prompt(id, None)` e
garanta que não reste agente em memória com o prompt anterior. Isso preserva
mensagens, histórico e roteamento; não use reset nem apague sessões para isso.

## Contrato vigente

O desenho atual está em
`docs/superpowers/specs/2026-09-01-hermes-equipe-multiagente-as-built-design.md`.
Os documentos de 24/08 são históricos.
O modo de manutenção pelo Telegram descrito acima atualiza a política de 01/09.

## Verificação manual da frota

A verificação completa é executada sob demanda:

```bash
/root/.hermes/ops/hermes-team/verify_team.py full
hermes gateway status --deep --system
hermes kanban diagnostics
curl --fail --silent http://127.0.0.1:3000/health
systemctl status hermes-whatsapp-healthcheck.timer --no-pager
git -C /root/.hermes status --short
```

O verificador deve retornar `PASS`, o health deve retornar `connected`, o
diagnóstico Kanban deve ser vazio e o Git deve estar limpo fora de uma mudança
deliberada em andamento.

## Gateways dos Profiles

```bash
for unit in \
  hermes-gateway.service \
  hermes-gateway-porteiro.service \
  hermes-gateway-cadastro.service \
  hermes-gateway-famaagent.service \
  hermes-gateway-reno.service \
  hermes-gateway-agendamento.service \
  hermes-gateway-dev.service
do
  systemctl is-active "$unit"
  systemctl is-enabled "$unit"
done
```

Todos devem responder `active` e `enabled`. Reinicie apenas a unit que falhou;
um gateway de especialista não possui dispatcher Kanban.

Se o Telegram do Agendamento for explicitamente desabilitado durante uma nova
troca de credencial/destino, `verify_team.py` e `fleet_watch.py` registram a
pendência sem declarar falha de gateway; a operação CLI continua disponível.
Ausência do Profile ou ausência de um estado Telegram explícito continuam erro.

### Como reiniciar

Use `hermes -p <profile> gateway restart`, e para o CEO `hermes gateway
restart`. **Não use `systemctl restart`**: ele manda SIGTERM e mata turno em
voo. O comando do Hermes envia SIGUSR1, que recusa turnos novos, espera o
trabalho em voo terminar até `agent.restart_after_turn_timeout` — 1800 s aqui —
e só então sai; o systemd sobe de volta.

Três coisas observadas em 2026-09-01 que valem saber antes:

- o comando **reescreve o arquivo `.service`** da unit; os drop-ins em `.d/`,
  inclusive `git-identity.conf`, sobrevivem;
- reiniciar o CEO **derruba o bridge do WhatsApp** por alguns segundos — a
  sessão persistida é reusada, sem novo pareamento;
- com conversa ativa, o restart pode levar até 30 minutos drenando. Isso é o
  comportamento correto, não travamento.

Ordem segura: especialistas primeiro, CEO por último, na janela de menor
tráfego.

```bash
for p in porteiro cadastro famaagent reno agendamento dev; do
  hermes -p $p gateway restart
done
hermes gateway restart
```

Nunca use `--all`: ela mata todos os processos de gateway antes de reiniciar.

## Falha do WhatsApp

1. Verificar `journalctl -u hermes-gateway.service --since "30 minutes ago"`.
2. Confirmar o health local e a existência de
   `/root/.hermes/platforms/whatsapp/session/creds.json`.
3. Reiniciar somente `hermes-gateway.service` uma vez.
4. Se a sessão estiver revogada, parar o gateway e executar `hermes whatsapp`
   em TTY para novo QR; não apagar sessão sem confirmar a revogação.
5. Se houver incompatibilidade de protocolo Baileys, não atualizar durante um
   incidente sem novo backup e plano específico de atualização Hermes.

## Falha de worker

1. Ler `hermes kanban show <task_id>` e `hermes kanban runs <task_id>`.
2. Não criar tarefa substituta para crash/timeout.
3. `max_retries: 2` permite somente uma retentativa após a inicial.
4. Dependência ausente deve permanecer bloqueada e ser escalada ao Renato.
5. Verificar o gateway do Profile atribuído sem reiniciar os demais.

## Cartões bloqueados

Liste apenas o estado antes de decidir qualquer mutação:

```bash
hermes kanban list --status blocked --json \
  | jq '[.[] | {id, title, assignee, status}]'
```

Leia o cartão e seus runs. Não faça retry, reatribuição ou cancelamento apenas
porque o status é `blocked`; identifique primeiro a dependência ou entrada
ausente.

Um bloqueio **já foi notificado** quando aconteceu: `auto_subscribe_on_create`
inscreve a sessão de origem, e o `last_event_id` da inscrição avança até o
evento `blocked`. Mas a notificação vai para a **conversa de origem** — em
cartão de lead, a DM do próprio lead, o que acorda o CEO ali dentro sem avisar
você. O aviso ao operador é feito pelo monitor externo
`hermes-fleet-watch.timer`, a cada cinco minutos, pelo bot Telegram do Dev.
O antigo cron de 15 minutos foi substituído; `profiles/dev/cron/jobs.json`
vazio não significa que o monitor externo esteja desligado.

## Mudança de MCP ou contrato

1. Trate `tools.include` como allowlist exata, nunca como exemplo.
2. Não exponha Brain/FamaChat no Telegram dos workers.
3. Atualize o SOUL/skill e `verify_team.py` no mesmo commit.
4. Execute os modos `core` e `full` antes de reiniciar qualquer gateway.
5. Para transição de etapa pelo Reno, preserve `expectedStatus` e somente as
   transições progressivas documentadas na especificação vigente.
6. Para agenda, preserve o encadeamento `Reno -> Agendamento -> Reno`, a
   allowlist exata de cinco ferramentas do Agendamento e a remoção das duas
   ferramentas de agenda do Reno.

## Conferência do handoff de agendamento

O pedido intermediário do Reno usa `decision: appointment_requested`, e o
resultado do Agendamento usa `decision: appointment_processed`. Ambos têm
`status: success`, `requested_next_action: return_to_ceo` e
`response_ready: null`. O `request_id` do pedido deve ser o ID real da tarefa
original do Reno; o resultado preserva pedido, cliente, corretor e operação.

Valide cópias JSON protegidas sem acessar rede ou dados reais:

```bash
python ops/hermes-team/appointment_handoff_check.py request \
  /caminho/protegido/reno-metadata.json \
  --original-task-id '<id-real-da-tarefa-reno>'

python ops/hermes-team/appointment_handoff_check.py result \
  /caminho/protegido/agendamento-metadata.json \
  --request /caminho/protegido/corpo-da-tarefa-agendamento.json
```

Saídas: `PASS: APPOINTMENT_REQUEST` ou `PASS: APPOINTMENT_RESULT` (0),
divergência de forma/identidade (1) e erro de leitura ou JSON (2). O validador
confere somente a forma e a correlação fornecida. Ele não chama o FamaChat, não
prova que o modelo seguirá as instruções comerciais, não confirma entrega pelo
CEO e não exige que o horário ainda esteja no futuro no instante da auditoria.

O monitor aceita um pedido válido do Reno como etapa intermediária, em vez de
`missing_response`. Tarefa do Agendamento em fila, travada ou falha segue os
alertas normais; resultado malformado gera `appointment_result_invalid` e
`outcome: pending` válido gera `appointment_pending` para atenção interna.
`needs_information` válido segue ao Reno para formular a pergunta ao cliente.

## Conferência do handoff CTWA para o Reno

O contrato de corpo está em `fama-ceo-runtime` e `fama-reno-runtime`:
`contexto.ctwa_attributions` preserva evento, origem e atribuição normalizada
da conversa atual. Atribuição pendente não segura o atendimento. Endereço e
demais fatos imobiliários continuam dependendo da verificação no FamaChat.

Teste isolado, sem acesso a serviços ou dados reais, a partir da raiz do checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python \
  -m unittest discover -s ops/hermes-team/tests -v
```

Para auditar um cartão já observado, use dois arquivos JSON locais protegidos:
o retorno de `conversation_context` da mesma conversa e o **body** do cartão
convertido em objeto JSON (não a chamada inteira nem uma string YAML):

```bash
python ops/hermes-team/ctwa_handoff_check.py \
  --context /caminho/protegido/context.json \
  --card /caminho/protegido/card-body.json
```

Saídas: `PASS: CTWA_HANDOFF` (0), divergências de contrato sem conteúdo dos dados
(1), erro de leitura/decodificação da entrada (2). O verificador não chama rede,
não grava arquivos nem modifica cartões. Não exporte conteúdo real para Git ou logs.

Este é um diagnóstico offline, **não um hook de `kanban_create`**: valida a
cópia recebida, mas não autentica a sessão, não prova entrega da resposta e
não faz detecção geral de PII/raw disfarçado como texto. `verify_team.py` continua
validando a instalação `/root/.hermes`, mesmo se invocado de um worktree.

Depois de uma ativação autorizada das instruções, valide um novo primeiro cartão
do Reno e a resposta final. Confira que o prompt usado realmente contém o novo
contrato: conversas existentes podem conservar instruções em cache. Não apague
sessões nem reabra cartões antigos para testar. Esta alteração não automatiza
preenchimento retroativo nem atualização quando uma atribuição pendente resolve.

## Rollback

1. Identificar os arquivos e a unit afetados; não parar gateways não
   relacionados.
2. Se WhatsApp ou configuração do CEO estiverem afetados, parar
   `hermes-gateway.service`.
3. Localizar o backup mais recente em `/root/hermes-rollout-backups/` e
   conferir seu `SHA256SUMS`.
4. Restaurar somente os arquivos afetados a partir de
   `live-config-and-dev.tgz` ou do backup Hermes.
5. Iniciar e validar somente as units afetadas e executar
   `verify_team.py full`.
6. Se o rollback remover o WhatsApp, desabilitar também
   `hermes-whatsapp-healthcheck.timer` para evitar alertas sem canal.


## Por que nao existe manifesto de checksums

Ate 2026-09-01 este diretorio guardava `DEPLOYED_SHA256SUMS`, um manifesto com
o sha256 de cada arquivo operacional implantado. Ele foi removido, e o motivo
importa mais que o arquivo.

De 90 entradas, 65 falhavam e 2 apontavam para arquivos que nao existiam mais.
Quarenta eram de arquivos volateis de runtime — `.update_check`, `cache/`,
snapshots de prompt, contadores de uso — que mudam sozinhos entre uma execucao
e outra. A primeira linha era o hash do proprio manifesto, capturado vazio, e
portanto nunca poderia conferir. Nenhum script, gate ou passo de runbook o
verificava: a unica referencia era uma captura unica num plano de 2026-08-24.

Um controle que nunca pode passar nao e obedecido, e um que ninguem executa nao
protege nada — mas quem o encontrasse suporia, com razao, que os arquivos
implantados estavam protegidos por checksum. Essa suposicao era o unico efeito
real que ele tinha.

O que de fato registra integridade aqui e o git: `/root/.hermes` e um
repositorio, e `git status` limpo com HEAD conhecido diz o que o manifesto
tentava dizer, sobre o conjunto certo de arquivos. O que registra contrato e o
`verify_team.py`, que verifica o conteudo que importa — `tools.include` exato,
exposicao MCP por plataforma, marcadores obrigatorios e proibidos de cada SOUL
e skill. Nenhum dos dois precisa de um terceiro registro pior.


## Incidentes de atendimento — 08/09/2026

Política do CEO: sem resposta válida, `[SILENT]` no WhatsApp e registro interno
no cartão com `INCIDENTE_ATENDIMENTO `. Um veredito normal de Porteiro/Cadastro
não precisa de texto ao cliente; retry em curso não é falha definitiva.

O vigia já instalado em `ops/observability/fleet_watch.py` incorpora
`attendance_incidents.py`. Ele detecta impedimentos no Kanban, espera na fila
acima de cinco minutos, execução acima do teto mais 60 segundos e mensagens
externas sem resposta registrada por 15 minutos. Contatos em atendimento humano
são excluídos dessa detecção; falhas de infraestrutura continuam monitoradas.
A checagem de ausência de resposta é conservadora: não interpreta “obrigado” nem
prova entrega no WhatsApp. O Dev investiga antes de recomendar ação.

Alertas de atendimento saem na primeira verificação; sinais gerais mantêm três
ocorrências. O destino é o home channel Telegram do Dev, lido do config atual.
Nenhuma chamada de envio depende do gateway, Kanban ou modelo. Credenciais são
lidas do `.env` do Dev e nunca aparecem em argumentos de processo ou logs.

Estado de envio e deduplicação: `/var/lib/hermes-fleet-watch` (0700; arquivos 0600).
O drop-in versionado `ops/observability/systemd/incident-channel.conf` configura
`StateDirectory`. Ao ativar, copie os três JSON de dedup de
`/run/hermes-fleet-watch` se ainda não houver estado persistente, sem apagar a
origem. O lock evita duas varreduras emitindo o mesmo alerta simultaneamente.
Os incidentes são persistidos em `pending.json` antes do envio e permanecem na
fila mesmo se o sinal desaparecer. Os alertas são limitados ao tamanho aceito
pelo Telegram; envio recusado retorna
exit 2 e continua pendente para a próxima varredura. Se o processo cair depois
que o Telegram aceitou e antes de gravar o recibo, pode haver reentrega; a
referência estável do incidente permite reconhecê-la.

Diagnóstico automático permanece somente leitura e limitado a três chamadas por
hora. Ao atingir o teto, o operador ainda recebe o alerta com a ação necessária.
Sinal ausente gera aviso de mudança de estado, nunca promessa de que o lead foi
respondido. Banco indisponível não fecha os incidentes de atendimento.

Para diagnóstico sem enviar alertas nem alterar estado:

```bash
/root/.hermes/ops/observability/fleet_watch.py --fast
systemctl status hermes-fleet-watch.timer hermes-fleet-watch.service --no-pager
```

Para validar código com dados sintéticos:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python \
  -m unittest discover -s /root/.hermes/ops/observability/tests -v
```

Não retome atendimento automaticamente. Confirme a correção, o último estado do
cartão, novas mensagens, respostas já emitidas e pausa humana. A marca
`INCIDENTE_ENCERRADO ` documenta uma resolução verificada; não substitui a
correção de um bloqueio nem autoriza replay.

Limite desta política: `[SILENT]` governa as respostas do CEO e os handoffs dos
especialistas. A instalação do Hermes ainda pode produzir diagnósticos próprios
no gateway (por exemplo timeout ou autenticação do provedor), fora do prompt do
CEO. Não há filtro de saída instalado por esta mudança; portanto ela não prova
silêncio absoluto do transporte em falhas do próprio gateway.


Atualização de instruções em conversas existentes: `refresh_ceo_policy.py`
usa a API nativa `SessionDB.update_system_prompt(id, None)` somente para
snapshots antigos de WhatsApp, Telegram e Kanban do CEO. O modo padrão apenas
conta; `--apply` exige CEO parado e deve executar em um `ExecStartPre` temporário
durante restart gracioso. Não altera mensagens, IDs, histórico ou roteamento.
A marca privada `ceo-policy-20260908.applied` torna a atualização única. Remova o
drop-in temporário depois da partida verificada; não faça reset de conversas.

## Aprendizagem automática — 08/09/2026

Os seis profiles têm `memory.memory_enabled: true`,
`memory.user_profile_enabled: true`, `memory.write_approval: false`,
`skills.write_approval: false`, `skills.ledger: true` e
`auxiliary.background_review.enabled: true`. A autorização permanente está em
`SOUL.md` e cobre memória e criação/atualização de skills, no primeiro plano e
na revisão automática, inclusive nos workers. Não exige pedido para salvar.

`memory.nudge_interval: 1` conta turnos de usuário;
`skills.creation_nudge_interval: 1` conta iterações de ferramenta. Essa frequência
permite revisar trabalhos curtos e aumenta o uso do modelo em comparação com o
intervalo anterior de 10. Sem aprendizado novo, `result=none` é um resultado
válido. Os modelos e a rota da revisão foram preservados.

A disponibilidade deve ser conferida pelo resolvedor nativo de ferramentas.
Composites que já incluem memória e skills são preservados; misturar nomes
inválidos com toolsets explícitos pode mudar o fallback. Nos canais WhatsApp,
foram acrescentadas somente as capacidades de aprendizagem que faltavam.

O plugin `fama-learning-lifecycle` fica em `ops/plugins/` e cada home tem um link
em `plugins/fama-learning-lifecycle`, com o nome incluído em `plugins.enabled`.
O hook oficial `on_session_finalize` espera as threads nativas `bg-review`
somente no CLI, antes do cleanup one-shot, com limite fixo padrão de 300 segundos.
Se o limite expirar, registra `pending > 0`; isso não comprova persistência.
Gateways mantêm revisão assíncrona. Nenhuma guarda de ferramenta foi removida.

Verificação reproduzível (sempre com o home explícito):

```bash
HERMES_HOME=/root/.hermes/profiles/porteiro /usr/local/lib/hermes-agent/venv/bin/python /root/.hermes/ops/hermes-team/verify_learning.py native
HERMES_HOME=/root/.hermes/profiles/porteiro /usr/local/lib/hermes-agent/venv/bin/python /root/.hermes/ops/hermes-team/verify_learning.py live
python3 -m unittest discover -s /root/.hermes/ops/hermes-team/tests -p test_learning_lifecycle.py -v
```

`native` cria entradas temporárias únicas, testa memória e criação/alteração de
skill com origem de revisão, recupera em outro processo e remove suas entradas.
`live` usa o modelo configurado, contadores naturais e o finalizador oficial;
pode salvar lições técnicas verificadas no próprio profile. Não usa CRM nem
envia mensagens. Confirme `Background review complete` e recupere a skill
salva em outro processo. Não confunda teste com contadores preparados com
execução natural: este verificador não prepara nem força os contadores.

Filhos de `delegate_task` continuam sujeitos ao bloqueio nativo da ferramenta
`memory`; o pai consolida as lições verificadas do filho. Não foi alterado o
código instalado do Hermes para contornar esse limite.

Após alterar instruções ou ferramentas de um gateway, salve os snapshots
anteriores, limpe somente o prompt e os nomes de ferramentas das sessões ativas
pelas APIs `SessionDB.update_system_prompt(id, None)` e
`SessionDB.update_session_tool_names(id, None)`, e use o reinício nativo que
aguarda turnos em andamento. Preserve mensagens, sessões e roteamento.

## Correção das divergências — 09/09/2026

Memória e skills são esperadas em todos os canais dos especialistas. O CLI mantém suas capacidades comerciais; Cadastro e FamaAgent usam `no_mcp` no Telegram administrativo. As 10 divergências anteriores foram resolvidas e o verificador `full` passou. Evidências em `TEAM-DIVERGENCES-RESOLVED.md`.
