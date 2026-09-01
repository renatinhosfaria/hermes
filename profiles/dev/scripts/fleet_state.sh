#!/bin/bash
# Fonte monitor do cron do Dev (hermes cron create --monitor-script).
#
# CONTRATO: a saida e comparada BYTE A BYTE por cron/monitor.py. Qualquer
# valor que muda sozinho (uptime, pid, timestamp, ordem de dicionario) faz
# todo tick virar falso positivo. Portanto: nada de horario, nada de pid,
# nada de uptime, e tudo ordenado.
set -uo pipefail
export PATH="/root/.local/bin:$PATH"

echo "## units"
for unit in \
  hermes-gateway.service \
  hermes-gateway-porteiro.service \
  hermes-gateway-cadastro.service \
  hermes-gateway-famaagent.service \
  hermes-gateway-reno.service \
  hermes-gateway-dev.service \
  hermes-whatsapp-healthcheck.timer
do
  printf '%s %s/%s\n' "$unit" \
    "$(systemctl is-active "$unit" 2>/dev/null || echo unknown)" \
    "$(systemctl is-enabled "$unit" 2>/dev/null || echo unknown)"
done

echo "## verify_team"
if /root/.hermes/ops/hermes-team/verify_team.py full >/dev/null 2>&1; then
  echo "PASS"
else
  echo "FAIL"
  # so as linhas de erro, ordenadas — o corpo informativo (matriz MCP) sai
  /root/.hermes/ops/hermes-team/verify_team.py full 2>&1 | grep -iE '^(ERRO|FAIL|- )' | sort
fi

echo "## kanban_diagnostics"
# Captura em variavel: um pipe vazio (hermes ausente/quebrado) nao gera linha
# alguma, entao um `sed s/^$/.../` no pipe NUNCA dispara e a falha sairia como
# linha em branco silenciosa. Testado: PATH sem hermes devolvia "" (len 0).
_diag=$(hermes kanban diagnostics --json 2>/dev/null | tr -d ' \n')
if [ -z "$_diag" ]; then
  echo "UNAVAILABLE"
else
  echo "$_diag"
fi

echo "## kanban_blocked"
python3 - <<'PY'
import sqlite3
try:
    c = sqlite3.connect('file:/root/.hermes/kanban.db?mode=ro', uri=True)
    rows = sorted(c.execute(
        "select id, assignee, coalesce(block_kind,'-') from tasks where status='blocked'"))
    print(f"count={len(rows)}")
    for r in rows:
        print(" ".join(str(x) for x in r))
except Exception as exc:
    print(f"UNAVAILABLE {type(exc).__name__}")
PY

echo "## whatsapp"
# so o campo status: uptime e queueLength mudam a cada chamada
curl --fail --silent --max-time 5 http://127.0.0.1:3000/health 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))" \
  2>/dev/null || echo "unreachable"

echo "## git_worktree"
# BINARIO de proposito: clean|dirty, sem a lista de arquivos. A lista muda a
# cada arquivo tocado, e num tick de 15min isso acordaria o agente varias vezes
# por sessao de trabalho, afogando o sinal de saude da frota no ruido de
# desenvolvimento. O agente roda `git status` sozinho quando acorda; o detalhe
# nao precisa estar nos bytes comparados.
if [ -z "$(git -C /root/.hermes status --porcelain 2>/dev/null)" ]; then
  echo "clean"
else
  echo "dirty"
fi

echo "## hermes_version"
hermes --version 2>/dev/null | head -1 | sed 's/ (.*//'
