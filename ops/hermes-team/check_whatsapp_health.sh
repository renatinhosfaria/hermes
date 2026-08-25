#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${WHATSAPP_HEALTH_STATE_DIR:-/run/hermes-whatsapp-healthcheck}"
HEALTH_URL="${WHATSAPP_HEALTH_URL:-http://127.0.0.1:3000/health}"
DRY_RUN="${WHATSAPP_HEALTH_DRY_RUN:-false}"
FORCE_ACTIVE="${WHATSAPP_HEALTH_FORCE_GATEWAY_ACTIVE:-false}"
FAIL_FILE="$STATE_DIR/failures"
ALERT_FILE="$STATE_DIR/alerted"

install -d -m 700 "$STATE_DIR"

if [[ "$FORCE_ACTIVE" != "true" ]] && ! systemctl is-active --quiet hermes-gateway.service; then
  exit 0
fi

if curl --fail --silent --max-time 8 "$HEALTH_URL" >/dev/null; then
  if [[ -f "$ALERT_FILE" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      printf '%s\n' "DRY_RUN: recuperação do WhatsApp seria enviada ao Telegram"
    else
      hermes send --to telegram "WhatsApp/Baileys voltou a responder no gateway Hermes."
    fi
  fi
  rm -f "$FAIL_FILE" "$ALERT_FILE"
  exit 0
fi

failures=0
if [[ -f "$FAIL_FILE" ]]; then
  read -r failures < "$FAIL_FILE" || failures=0
fi
if ! [[ "$failures" =~ ^[0-9]+$ ]]; then
  failures=0
fi
failures=$((failures + 1))
printf '%s\n' "$failures" > "$FAIL_FILE"
chmod 600 "$FAIL_FILE"

if (( failures >= 3 )) && [[ ! -f "$ALERT_FILE" ]]; then
  if [[ "$DRY_RUN" == "true" ]]; then
    printf '%s\n' "DRY_RUN: alerta persistente do WhatsApp seria enviado ao Telegram"
  else
    hermes send --to telegram "Alerta Hermes: WhatsApp/Baileys falhou em três verificações consecutivas."
  fi
  install -m 600 /dev/null "$ALERT_FILE"
fi
