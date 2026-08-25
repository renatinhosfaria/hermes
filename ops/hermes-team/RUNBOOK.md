# Runbook — Equipe Hermes da Fama

## Estado esperado

- Gateway ativo: `hermes-gateway.service`.
- Gateway `dev`: disabled/inactive.
- Profiles: `default`, `porteiro`, `cadastro`, `famaagent`, `reno`, `dev`.
- Kanban: dispatcher no gateway, decomposição automática desligada.
- Telegram: somente Renato pela allowlist.
- WhatsApp: modo bot, DMs abertas, grupos desabilitados.
- Alerta de WhatsApp: `hermes-whatsapp-healthcheck.timer` ativo; alerta após
  três falhas consecutivas e mensagem de recuperação quando o health volta.
- MCP FamaChat: não configurado.

## Verificação diária

```bash
/root/.hermes/ops/hermes-team/verify_team.py full
hermes gateway status --deep --system
hermes kanban diagnostics
curl --fail --silent http://127.0.0.1:3000/health
systemctl status hermes-whatsapp-healthcheck.timer --no-pager
```

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

## Rollback

1. Parar `hermes-gateway.service`.
2. Localizar o backup mais recente em `/root/hermes-rollout-backups/` e
   conferir seu `SHA256SUMS`.
3. Restaurar somente os arquivos afetados a partir de
   `live-config-and-dev.tgz` ou do backup Hermes.
4. Iniciar e validar `hermes-gateway.service`.
5. Reabilitar `hermes-gateway-dev.service` somente se o gateway principal não
   puder prestar o serviço e Renato autorizar o rollback temporário.
6. Se o rollback remover o WhatsApp, desabilitar também
   `hermes-whatsapp-healthcheck.timer` para evitar alertas sem canal.
