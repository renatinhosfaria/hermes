# Runbook — Equipe Hermes da Fama

## Estado esperado

- Gateways ativos e habilitados: `hermes-gateway.service` e os gateways
  `porteiro`, `cadastro`, `famaagent`, `reno` e `dev`.
- Profiles: `default`, `porteiro`, `cadastro`, `famaagent`, `reno`, `dev`.
- Modelos: CEO e Dev em `gpt-5.6-sol-900k`; demais Profiles em
  `gpt-5.6-luna-900k`.
- Kanban: dispatcher somente no gateway do CEO; `dispatch_in_gateway: false`
  nos cinco especialistas; decomposição automática desligada.
- Telegram: somente Renato pela allowlist, com home channel exclusivo por
  Profile.
- WhatsApp: modo bot, DMs abertas, grupos desabilitados.
- Alerta de WhatsApp: `hermes-whatsapp-healthcheck.timer` ativo; alerta após
  três falhas consecutivas e mensagem de recuperação quando o health volta.
- MCPs: Brain/FamaChat somente nos Profiles e contextos permitidos por
  `verify_team.py`; não são expostos nos canais Telegram dos workers.

## Contrato vigente

O desenho atual está em
`docs/superpowers/specs/2026-09-01-hermes-equipe-multiagente-as-built-design.md`.
Os documentos de 24/08 são históricos.

## Verificação diária

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
  hermes-gateway-dev.service
do
  systemctl is-active "$unit"
  systemctl is-enabled "$unit"
done
```

Todos devem responder `active` e `enabled`. Reinicie apenas a unit que falhou;
um gateway de especialista não possui dispatcher Kanban.

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

## Mudança de MCP ou contrato

1. Trate `tools.include` como allowlist exata, nunca como exemplo.
2. Não exponha Brain/FamaChat no Telegram dos workers.
3. Atualize o SOUL/skill e `verify_team.py` no mesmo commit.
4. Execute os modos `core` e `full` antes de reiniciar qualquer gateway.
5. Para transição de etapa pelo Reno, preserve `expectedStatus` e somente as
   transições progressivas documentadas na especificação vigente.

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
