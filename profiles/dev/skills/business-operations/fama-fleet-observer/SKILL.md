---
name: fama-fleet-observer
description: "Use ao investigar um alerta do vigia da frota Hermes/Brain."
license: MIT
metadata:
  version: 1.0.0
  author: Fama Negócios Imobiliários
  platforms: [linux]
  hermes:
    tags: [fama, dev, observabilidade, frota, diagnóstico, incidente]
---

# Investigação de alerta da frota

Use quando o vigia (`hermes-fleet-watch.timer`) apontar um problema. O vigia
detecta e avisa; ele não diagnostica. Seu trabalho é dizer **o que quebrou, por
quê, e qual a ação recomendada** — e parar aí.

## Primeira regra: leia o relatório antes de qualquer comando

```bash
jq -s '.[-1]' /var/log/hermes-fleet-watch/report.jsonl
```

Cada achado traz `severity`, `area`, `message` e `sig` (a assinatura estável).
O bloco `health_raw` guarda a resposta crua dos três endpoints de saúde. Muita
investigação termina aqui, sem rodar mais nada.

Use `jq`, nunca um pipe para `python3`: o scanner de segurança do seu terminal
recusa invocação de interpretador, e o comando falha antes de rodar. Onde uma
consulta a banco for necessária, existe sub-rotina pronta — veja abaixo.

## Segunda regra: confirme antes de concluir

Você vai encontrar sintomas que parecem causas. Duas armadilhas reais já
custaram horas nesta frota:

- **Fila cheia não é dado perdido.** Um evento parado na fila de saída do
  observer pode já estar gravado no Brain. Confira antes de tratar como perda.
- **O erro que aparece no log pode ser consequência.** Colisões de spool
  (`upsert_processing_failed`) são efeito de um evento preso, não a causa dele.

Quando o log não disser o motivo, **reproduza a requisição** em vez de supor.
Foi assim que se descobriu um `TRANSPORT_REQUEST_INVALID` que nenhum log
registrava.

## Roteiro por classe de falha

### `systemd` — unit inativa ou reiniciando

```bash
systemctl status <unit> --no-pager -n 30
journalctl -u <unit> --since '-1h' --no-pager | tail -40
```
Em gateway, cheque também a morte suja e o loop de restart:
`<HERMES_HOME>/logs/gateway-exit-diag.log` (JSONL) e
`<HERMES_HOME>/state/gateway.lifecycle.json`.

Restart de gateway **não é sua decisão**: relate e pare.

### `gateway` — heartbeat parado ou saída suja

O heartbeat vive em `<HERMES_HOME>/state/gateway.heartbeat` e traz `rss_kib` e
`mem_available_kib`. Unit `active` com heartbeat velho significa event loop
travado, não processo morto — distinga os dois no relato.

```bash
hermes logs errors --since 1h --component gateway
hermes -p <profile> status --deep
```

### `kanban` — run com `crashed`, `timed_out` ou `gave_up`

```bash
hermes kanban diagnostics --json
hermes kanban runs <task_id>
hermes kanban log <task_id>
tail -50 /root/.hermes/kanban/logs/t_<task_id>.log
```
`gave_up` é o disjuntor após `consecutive_failures`; `crashed` é PID morto sem
limpeza. `protocol_violation` significa que o worker saiu limpo sem chamar
`kanban_complete` — quase sempre bug do prompt, não da infra.

### `brain` — health degradado ou `lifecycle_effects` presos

```bash
curl -s 127.0.0.1:8765/health | jq .
journalctl -u brain.service --since '-1h' --no-pager | grep brain_conversation_access
```
As linhas `brain.audit` são JSON com `decision` (`allow`/`deny`/`unavailable`),
`tool`, `profile` e `error`. Um `deny` recorrente com `AUTH_SESSION_MISMATCH`
aponta contexto de execução, não credencial.

### `brain_observer` — fila de saída presa

**Antes de tudo, veja se o dado já está salvo:**

```bash
/root/.hermes/ops/observability/fleet_watch.py --check-ingested
```

Ele compara cada evento parado na fila com a tabela `transport_events` do Brain
(leitura somente-leitura) e diz qual das duas coisas você tem:

- **Todos JA SALVO** — são duplicatas. Não há perda de dado; a fila está mal
  varrida, não entupida. A urgência cai, e o problema é de limpeza.
- **Algum AUSENTE** — aí sim há risco de perda, e o prazo importa: a purga
  descarta o arquivo 72 h depois do `spooled_at`.

Confundir os dois casos já custou horas nesta frota. Depois:

```bash
journalctl -u brain-whatsapp-observer.service --since '-6h' --no-pager \
  | grep '"component":"brain-whatsapp-observer"'
journalctl -u brain.service --since '-6h' --no-pager | grep 'transport/events'
```

Falha permanente é definitiva enquanto o processo viver: fica numa lista em
memória e o arquivo não sai da fila até a purga de 72h.

### `filas` — `delivery_obligations` em `failed`/`abandoned`

Bancos vivos: leia sempre em `mode=ro` com `PRAGMA query_only=ON`. Nunca abra
`state.db` ou `kanban.db` para escrita — você trava o gateway.

### `logs` — volume de ERROR acima do normal

```bash
hermes logs errors --since 1h --level ERROR -n 100
```
Agrupe por logger antes de concluir. Um logger dominante é uma causa; erros
espalhados são sintoma de algo abaixo.

### `integridade` — instalação do Hermes modificada

```bash
git -C /usr/local/lib/hermes-agent status --porcelain
```
Não deve ter saída **nunca**. Se tiver, é incidente: relate imediatamente e não
tente reverter por conta própria.

## Limites

Você observa e diagnostica. **Não** reinicia serviço, **não** altera profile,
**não** apaga arquivo de fila, **não** mexe em banco. Tudo isso exige
autorização prévia e explícita do Renato — as regras do seu SOUL.md e do
`.hermes.md` continuam valendo integralmente aqui.

Se a correção for óbvia, descreva-a como recomendação, com o comando exato que
você rodaria. Quem decide executar é o Renato.

## Formato do relato

Curto e em pt-BR, nesta ordem:

1. **O que quebrou** — uma frase.
2. **Evidência** — o comando e o trecho da saída que provam.
3. **Causa** — ou, se não deu para determinar, diga isso e o que falta para
   determinar. Suposição apresentada como causa é pior que "não sei".
4. **Ação recomendada** — comando exato, e o risco de rodá-lo.
5. **Urgência real** — há perda de dado, ou só ruído? Diga qual das duas.

Ver também [[fama-dev-runtime]] para o contrato geral de mudanças.
