#!/usr/local/lib/hermes-agent/venv/bin/python
"""Vigia da frota Hermes + Brain.

Roda FORA do Hermes (systemd timer), sem LLM e sem tokens. A doc oficial do
Hermes proibe vigiar o gateway de dentro dele mesmo:

  "For critical system-health watchdogs that must fire even when the gateway
   is down, use OS-level cron"      -- guides/cron-script-only.md
  "Don't alert the gateway about itself"  -- guides/pipe-script-output.md

Por isso: toda leitura e read-only, o alerta sai diretamente na API do
Telegram (nunca `hermes send`), e nenhum banco vivo e aberto para escrita.

Saida: um relatorio JSON no stdout. Exit 0 = tudo bem, 1 = ha achados.
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

from attendance_incidents import detect as detect_attendance
from datetime import datetime, timezone
from pathlib import Path

HERMES_ROOT = Path("/root/.hermes")
PROFILES = ["default", "dev", "reno", "agendamento", "porteiro", "cadastro", "famaagent"]

UNITS = [
    "hermes-gateway.service",
    "hermes-gateway-dev.service",
    "hermes-gateway-reno.service",
    "hermes-gateway-agendamento.service",
    "hermes-gateway-porteiro.service",
    "hermes-gateway-cadastro.service",
    "hermes-gateway-famaagent.service",
    "hermes-whatsapp-healthcheck.timer",
    "brain.service",
    "brain-whatsapp-observer.service",
]

PENDING_TELEGRAM_GATEWAYS = {
    "hermes-gateway-agendamento.service": "agendamento",
}

# Limiares. Mantidos conservadores para nao gerar falso positivo na 1a rodada.
GATEWAY_HEARTBEAT_MAX_AGE = 300      # s; heartbeat do gateway parado
OUTBOX_MAX_AGE = 3600                # s; evento presa no outbox do observer
DELIVERY_MAX_AGE = 1800              # s; obrigacao de entrega pendente
ERRORS_LOG_WINDOW = 3600             # s; janela para contar ERROR
ERRORS_LOG_THRESHOLD = 20            # ERROR na janela por profile
RESTART_THRESHOLD = 3                # restarts recentes de uma unit

HEALTH_ENDPOINTS = {
    "brain": "http://127.0.0.1:8765/health",
    "observer_whatsapp": "http://127.0.0.1:8775/health",
    "bridge_whatsapp": "http://127.0.0.1:3000/health",
}


def now() -> float:
    return time.time()


def finding(sev: str, area: str, msg: str, **extra) -> dict:
    """Um achado. `sig` e a assinatura estavel usada para deduplicar alertas."""
    f = {"severity": sev, "area": area, "message": msg}
    f.update(extra)
    f["sig"] = f"{area}:{extra.get('key', msg)[:80]}"
    return f


# ---------------------------------------------------------------- systemd

def check_units() -> list[dict]:
    out = []
    for unit in UNITS:
        pending_profile = PENDING_TELEGRAM_GATEWAYS.get(unit)
        if pending_profile and telegram_explicitly_disabled(pending_profile):
            out.append(finding(
                "warning", "telegram",
                f"[{pending_profile}] Telegram pendente de credencial e destino; gateway não esperado",
                key=f"{pending_profile}_pending", pending=True, report_only=True,
            ))
            continue
        try:
            r = subprocess.run(
                ["systemctl", "show", unit,
                 "--property=ActiveState,SubState,NRestarts,Result"],
                capture_output=True, text=True, timeout=15,
            )
            props = dict(
                line.split("=", 1)
                for line in r.stdout.strip().splitlines() if "=" in line
            )
        except Exception as e:
            out.append(finding("error", "systemd",
                               f"nao consegui consultar {unit}: {type(e).__name__}",
                               key=unit))
            continue

        state = props.get("ActiveState", "unknown")
        if state not in ("active", "activating"):
            out.append(finding("critical", "systemd",
                               f"{unit} esta {state} ({props.get('SubState')})",
                               key=unit, active_state=state,
                               result=props.get("Result")))
        try:
            n = int(props.get("NRestarts", "0"))
        except ValueError:
            n = 0
        if n >= RESTART_THRESHOLD:
            out.append(finding("warning", "systemd",
                               f"{unit} reiniciou {n}x desde o ultimo reset",
                               key=f"{unit}:restarts", nrestarts=n))
    return out


def telegram_explicitly_disabled(profile: str) -> bool:
    """Only an explicit false suppresses that profile's Telegram gateway probe."""
    home = HERMES_ROOT if profile == "default" else HERMES_ROOT / "profiles" / profile
    try:
        import yaml
        config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
        telegram = ((config or {}).get("platforms") or {}).get("telegram") or {}
        return telegram.get("enabled") is False
    except (OSError, TypeError, yaml.YAMLError):
        return False


# ---------------------------------------------------------------- health HTTP

def http_json(url: str, timeout: float = 8.0):
    """Retorna (status_code, corpo_json_ou_texto). Nao levanta."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def check_health() -> tuple[list[dict], dict]:
    out, raw = [], {}
    for name, url in HEALTH_ENDPOINTS.items():
        code, body = http_json(url)
        raw[name] = {"status_code": code, "body": body}

        if code is None:
            out.append(finding("critical", "health",
                               f"{name} inalcancavel em {url} ({body})", key=name))
            continue
        if not isinstance(body, dict):
            out.append(finding("warning", "health",
                               f"{name} respondeu HTTP {code} sem JSON", key=name))
            continue

        status = body.get("status")
        if code != 200 or status not in ("ok", "connected"):
            out.append(finding("critical" if code != 200 else "warning", "health",
                               f"{name} status={status} (HTTP {code})",
                               key=name, detail=body))

        # Sinais especificos do observer do Brain.
        if name == "observer_whatsapp":
            age = body.get("outbox_oldest_age_seconds") or 0
            depth = body.get("outbox_depth") or 0
            if depth and age > OUTBOX_MAX_AGE:
                out.append(finding("critical", "brain_observer",
                                   f"outbox preso: {depth} evento(s), o mais antigo "
                                   f"ha {int(age/3600)}h",
                                   key="outbox_stuck", depth=depth, age_seconds=age))
            for field in ("permanent_failure_count", "unresolved_identity_count",
                          "raw_capture_failure_count"):
                v = body.get(field) or 0
                if v:
                    out.append(finding("warning", "brain_observer",
                                       f"{field}={v}", key=field, value=v))
    return out, raw


# ---------------------------------------------------------------- SQLite (ro)

def ro_connect(path: Path) -> sqlite3.Connection | None:
    """Abre em modo somente-leitura. Nunca cria nem trava o banco."""
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only = ON")
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def check_kanban() -> list[dict]:
    out = []
    conn = ro_connect(HERMES_ROOT / "kanban.db")
    if conn is None:
        return [finding("warning", "kanban", "kanban.db ilegivel", key="db")]
    try:
        # started_at/ended_at sao epoch inteiro, nao texto: datetime() sobre
        # eles nunca casa e a checagem devolvia zero em qualquer cenario --
        # falso-negativo silencioso, que e pior do que nao ter a checagem.
        rows = conn.execute("""
            SELECT outcome, COUNT(*) AS n FROM task_runs
            WHERE outcome IN ('crashed','timed_out','gave_up','spawn_failed')
              AND COALESCE(ended_at, started_at) >= strftime('%s','now') - 86400
            GROUP BY outcome
        """).fetchall()
        for r in rows:
            out.append(finding("critical" if r["outcome"] != "gave_up" else "warning",
                               "kanban",
                               f"{r['n']} run(s) com outcome={r['outcome']} nas ultimas 24h",
                               key=f"run_{r['outcome']}", count=r["n"]))

        rows = conn.execute("""
            SELECT id, assignee, consecutive_failures,
                   substr(COALESCE(last_failure_error,''),1,160) AS err
            FROM tasks
            WHERE status='blocked' AND COALESCE(consecutive_failures,0) > 0
            ORDER BY consecutive_failures DESC LIMIT 10
        """).fetchall()
        for r in rows:
            out.append(finding("warning", "kanban",
                               f"task {r['id']} ({r['assignee']}) bloqueada apos "
                               f"{r['consecutive_failures']} falha(s)",
                               key=f"blocked_{r['id']}", error=r["err"]))
    except sqlite3.Error as e:
        out.append(finding("warning", "kanban",
                           f"consulta falhou: {type(e).__name__}", key="query"))
    finally:
        conn.close()
    return out


def check_queues() -> list[dict]:
    """Filas de entrega e delegacao no state.db de cada profile."""
    out = []
    for profile in PROFILES:
        home = HERMES_ROOT if profile == "default" else HERMES_ROOT / "profiles" / profile
        conn = ro_connect(home / "state.db")
        if conn is None:
            continue
        try:
            rows = conn.execute("""
                SELECT state, COUNT(*) AS n,
                       MAX(strftime('%s','now') - created_at) AS age
                FROM delivery_obligations
                WHERE state IN ('pending','attempting','failed','abandoned')
                GROUP BY state
            """).fetchall()
            for r in rows:
                age = r["age"] or 0
                if r["state"] in ("failed", "abandoned"):
                    out.append(finding("critical", "filas",
                                       f"[{profile}] {r['n']} entrega(s) em "
                                       f"'{r['state']}'",
                                       key=f"{profile}_deliv_{r['state']}",
                                       count=r["n"]))
                elif age > DELIVERY_MAX_AGE:
                    out.append(finding("warning", "filas",
                                       f"[{profile}] {r['n']} entrega(s) em "
                                       f"'{r['state']}' ha {int(age/60)} min",
                                       key=f"{profile}_deliv_{r['state']}_old",
                                       count=r["n"], age_seconds=age))
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return out


def check_brain_runtime() -> list[dict]:
    out = []
    conn = ro_connect(Path("/var/lib/brain/runtime/brain-runtime.db"))
    if conn is None:
        return out
    try:
        rows = conn.execute("""
            SELECT state, COUNT(*) AS n FROM lifecycle_effects
            WHERE state IN ('permanent_failure','retryable','conflict')
            GROUP BY state
        """).fetchall()
        for r in rows:
            out.append(finding("critical" if r["state"] == "permanent_failure"
                               else "warning", "brain",
                               f"lifecycle_effects: {r['n']} em '{r['state']}'",
                               key=f"effects_{r['state']}", count=r["n"]))
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------- gateway/logs

def check_gateway_heartbeats() -> list[dict]:
    """Heartbeat que o proprio gateway grava. Um gateway vivo mas travado
    (event loop parado) fica 'active' no systemd e mesmo assim para aqui."""
    out = []
    for profile in PROFILES:
        home = HERMES_ROOT if profile == "default" else HERMES_ROOT / "profiles" / profile
        hb = home / "state" / "gateway.heartbeat"
        if not hb.exists():
            continue
        try:
            age = now() - hb.stat().st_mtime
            if age > GATEWAY_HEARTBEAT_MAX_AGE:
                out.append(finding("critical", "gateway",
                                   f"[{profile}] heartbeat parado ha {int(age)}s",
                                   key=f"{profile}_heartbeat", age_seconds=int(age)))
            data = json.loads(hb.read_text())
            mem = data.get("mem") or {}
            avail = mem.get("mem_available_kib")
            if isinstance(avail, int) and avail < 256 * 1024:
                out.append(finding("warning", "gateway",
                                   f"[{profile}] memoria disponivel baixa: "
                                   f"{avail // 1024} MiB",
                                   key=f"{profile}_mem", available_mib=avail // 1024))
        except Exception:
            continue
    return out


def check_unclean_exits() -> list[dict]:
    """O ledger de lifecycle marca morte suja (SIGKILL/OOM)."""
    out = []
    for profile in PROFILES:
        home = HERMES_ROOT if profile == "default" else HERMES_ROOT / "profiles" / profile
        lc = home / "state" / "gateway.lifecycle.json"
        if not lc.exists():
            continue
        try:
            data = json.loads(lc.read_text())
        except Exception:
            continue
        if data.get("phase") == "running" and data.get("previous_unclean_exit"):
            out.append(finding("warning", "gateway",
                               f"[{profile}] saida suja detectada no ultimo start",
                               key=f"{profile}_unclean"))
    return out


def check_errors_log() -> list[dict]:
    """Volume de ERROR na janela recente, por profile."""
    out = []
    cutoff = datetime.now() - __import__("datetime").timedelta(seconds=ERRORS_LOG_WINDOW)
    for profile in PROFILES:
        home = HERMES_ROOT if profile == "default" else HERMES_ROOT / "profiles" / profile
        log = home / "logs" / "errors.log"
        if not log.exists():
            continue
        count, loggers = 0, {}
        try:
            with log.open("r", errors="replace") as fh:
                # Le so o fim do arquivo: erro recente e o que importa.
                fh.seek(max(0, log.stat().st_size - 512 * 1024))
                fh.readline()
                for line in fh:
                    if " ERROR" not in line:
                        continue
                    try:
                        ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    if ts < cutoff:
                        continue
                    count += 1
                    parts = line.split(": ", 1)[0].split()
                    if parts:
                        loggers[parts[-1]] = loggers.get(parts[-1], 0) + 1
        except Exception:
            continue
        if count >= ERRORS_LOG_THRESHOLD:
            top = sorted(loggers.items(), key=lambda kv: -kv[1])[:3]
            out.append(finding("warning", "logs",
                               f"[{profile}] {count} ERROR na ultima hora "
                               f"(top: {', '.join(f'{k}={v}' for k, v in top)})",
                               key=f"{profile}_errors", count=count))
    return out


# ---------------------------------------------------------------- cron/integridade

def check_cron_doctor() -> list[dict]:
    """`hermes cron doctor` sai != 0 quando ha algo acionavel. Feito para
    watchdog, segundo a propria doc."""
    out = []
    for profile in PROFILES:
        try:
            r = subprocess.run(
                ["/root/.local/bin/hermes", "-p", profile, "cron", "doctor"],
                capture_output=True, text=True, timeout=90,
            )
        except Exception:
            continue
        if r.returncode not in (0, 2):
            detail = (r.stdout or r.stderr).strip().splitlines()
            if detail:
                out.append(finding("warning", "cron",
                                   f"[{profile}] cron doctor: {detail[0][:160]}",
                                   key=f"{profile}_cron_doctor"))
    return out


def check_integrity() -> list[dict]:
    out = []
    try:
        r = subprocess.run(
            ["git", "-C", "/usr/local/lib/hermes-agent", "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        )
        if r.stdout.strip():
            n = len(r.stdout.strip().splitlines())
            out.append(finding("critical", "integridade",
                               f"instalacao do Hermes modificada: {n} arquivo(s)",
                               key="hermes_dirty", count=n))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- alerta

STATE_DIR = Path(os.environ.get("FLEET_WATCH_STATE_DIR", "/var/lib/hermes-fleet-watch"))
FAILURE_STREAK = int(os.environ.get("FLEET_WATCH_STREAK", "3"))
DEV_ENV = Path("/root/.hermes/profiles/dev/.env")
DEV_CONFIG = Path("/root/.hermes/profiles/dev/config.yaml")

# Acordar o Dev custa tokens; alertar nao custa nada. Por isso o modelo so e
# chamado para assinatura inedita, no maximo INVESTIGATION_HOURLY_CAP por hora,
# e com o modelo leve. O monitor anterior desta frota foi removido depois de
# queimar 3,5M de tokens em 22h justamente por acordar o agente a cada mudanca.
INVESTIGATION_HOURLY_CAP = int(os.environ.get("FLEET_WATCH_INVESTIGATION_CAP", "3"))
INVESTIGATION_MODEL = os.environ.get("FLEET_WATCH_MODEL", "gpt-5.6-luna-900k")
INVESTIGATION_REASONING = os.environ.get("FLEET_WATCH_REASONING", "medium")
# 900s, nao 600: a primeira investigacao real levou 395s (66% do teto antigo).
# Um incidente com mais sinais para correlacionar estouraria, e a mensagem
# "nao consegui diagnosticar" e pior que esperar mais um minuto. O gasto segue
# limitado pelo teto horario, nao pelo relogio.
INVESTIGATION_TIMEOUT = int(os.environ.get("FLEET_WATCH_INVESTIGATION_TIMEOUT", "900"))
HERMES_BIN = os.environ.get("FLEET_WATCH_HERMES_BIN", "/root/.local/bin/hermes")


def load_state(name: str) -> dict:
    try:
        data = json.loads((STATE_DIR / name).read_text())
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("invalid watcher state")
    return data


def save_state(name: str, data: dict) -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = STATE_DIR / f".{name}.{os.getpid()}.tmp"
    with tmp.open("w") as fh:
        os.chmod(tmp, 0o600)
        json.dump(data, fh)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(STATE_DIR / name)
    fd = os.open(STATE_DIR, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_bot_token() -> str | None:
    """Le o token do .env do Dev. Nunca loga o valor."""
    try:
        for line in DEV_ENV.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"") or None
    except Exception:
        return None
    return None


def send_telegram(text: str) -> bool:
    """Independent delivery through the configured Dev bot. Never expose credentials."""
    if os.environ.get("FLEET_WATCH_DRY_RUN"):
        print(f"[DRY_RUN] enviaria:\n{text}", file=sys.stderr)
        return False  # a preview is never a delivery receipt
    token = read_bot_token()
    if not token:
        print("ERRO: token Telegram do Dev ausente", file=sys.stderr)
        return False
    try:
        import yaml
        config = yaml.safe_load(DEV_CONFIG.read_text())
        telegram = config["platforms"]["telegram"]
        channel = telegram["home_channel"]
        if not telegram.get("enabled") or channel.get("platform") != "telegram":
            raise ValueError("Dev Telegram disabled")
        chat_id = str(channel["chat_id"])
        if not chat_id.lstrip("-").isdigit():
            raise ValueError("invalid destination")
        body = {"chat_id": chat_id, "text": text}
        thread = str(channel.get("thread_id") or "")
        # General (1) rejects explicit thread IDs on this configured forum.
        if thread and thread != "1":
            body["message_thread_id"] = int(thread)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if result.get("ok") is True:
            return True
        print("ERRO: Telegram recusou alerta", file=sys.stderr)
    except Exception as exc:
        # Exception messages may contain the request URL and its bot token.
        print(f"ERRO: envio Telegram falhou ({type(exc).__name__})", file=sys.stderr)
    return False


def investigation_slots_left(state: dict) -> int:
    """Quantas investigacoes ainda cabem na janela de uma hora."""
    cutoff = now() - 3600
    state["recent"] = [t for t in state.get("recent", []) if t > cutoff]
    return max(0, INVESTIGATION_HOURLY_CAP - len(state["recent"]))


def request_investigation(finding: dict) -> bool:
    """Dispara a investigacao fora deste processo e volta na hora.

    O vigia roda num oneshot com timeout curto e o timer nao pode ficar parado
    esperando um agente. `systemd-run` cria uma unidade transitoria propria, com
    teto de tempo e log no journal, entao a analise nao atrasa a proxima
    varredura nem morre junto com o cgroup deste servico.
    """
    token = hashlib.sha256(finding["sig"].encode()).hexdigest()[:16]
    request = STATE_DIR / f"investigate-{token}.json"
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        request.write_text(json.dumps(finding))
        # systemd-run parte de um ambiente limpo, entao as sobrescritas
        # FLEET_WATCH_* precisam ser repassadas explicitamente -- sem isto a
        # investigacao ignora silenciosamente a configuracao do operador.
        setenv = [f"--setenv={k}={v}" for k, v in os.environ.items()
                  if k.startswith("FLEET_WATCH_")]
        subprocess.run(
            ["systemd-run", "--collect", "--quiet",
             f"--unit=hermes-fleet-investigate-{token}",
             f"--property=RuntimeMaxSec={INVESTIGATION_TIMEOUT + 60}",
             *setenv,
             str(Path(__file__).resolve()), "--investigate", str(request)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return True
    except Exception as e:
        detail = getattr(e, "stderr", "") or str(e)
        print(f"ERRO: nao consegui iniciar a investigacao: {str(detail)[:200]}",
              file=sys.stderr)
        request.unlink(missing_ok=True)
        return False


def run_investigation(request_path: str) -> int:
    """Modo `--investigate`: pede o diagnostico ao Dev e entrega o resultado."""
    path = Path(request_path)
    try:
        finding = json.loads(path.read_text())
    except Exception as e:
        print(f"ERRO: pedido ilegivel: {e}", file=sys.stderr)
        return 1

    relacionados = finding.get("related") or []
    contexto = ""
    if relacionados:
        # Os irmaos do mesmo incidente entram como contexto, nao como
        # investigacao separada: sao o mesmo evento visto de outro angulo.
        contexto = ("outros achados da mesma area, provavelmente o mesmo "
                    "incidente:\n" + "\n".join(f"- {m}" for m in relacionados) + "\n\n")
    prompt = (
        "O vigia da frota detectou um problema novo. Investigue e relate.\n\n"
        f"severity: {finding.get('severity')}\n"
        f"area: {finding.get('area')}\n"
        f"achado: {finding.get('message')}\n\n"
        f"{contexto}"
        f"O relatorio completo esta em {REPORT_PATH} (ultima linha). "
        "Siga a skill fama-fleet-observer: leia o relatorio antes de rodar "
        "comandos, confirme antes de concluir, e nao altere nada. "
        "Responda no formato de relato da skill, em pt-BR."
    )
    saida = ""
    try:
        result = subprocess.run(
            [HERMES_BIN, "-p", "dev", "chat", "-Q", "-q", prompt,
             "-s", "fama-fleet-observer",
             "-m", INVESTIGATION_MODEL, "--reasoning", INVESTIGATION_REASONING],
            capture_output=True, text=True, timeout=INVESTIGATION_TIMEOUT,
        )
        saida = (result.stdout or "").strip()
    except subprocess.TimeoutExpired:
        print("ERRO: investigacao estourou o tempo", file=sys.stderr)
    except Exception as e:
        print(f"ERRO: investigacao falhou: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        path.unlink(missing_ok=True)

    # A primeira linha do -Q e o session_id, ruido para quem le no Telegram.
    corpo = "\n".join(
        l for l in saida.splitlines() if not l.startswith("session_id:")
    ).strip()
    if not corpo:
        send_telegram(
            f"🔎 Dev nao conseguiu diagnosticar: {finding.get('area')} — "
            f"{finding.get('message')}\n\n"
            "Sem saida do agente. Ver `journalctl -u hermes-fleet-investigate-*`."
        )
        return 1
    # Telegram corta em 4096; a margem cobre o cabecalho.
    send_telegram(f"🔎 Diagnostico do Dev — {finding.get('area')}\n\n{corpo[:3500]}")
    return 0


def run_check_ingested() -> int:
    """Modo `--check-ingested`: a fila do observer esta presa, ou so mal varrida?

    Existe como sub-rotina, e nao como receita na skill, por dois motivos: o
    `sqlite3` de linha de comando nao esta instalado, e o scanner de seguranca
    do Dev recusa invocacao de interpretador com codigo embutido. Alem disso a
    licao vira ferramenta: um evento parado na fila pode ja estar gravado no
    Brain, e confundir as duas coisas custou horas de investigacao.
    """
    outbox = Path(os.environ.get(
        "FLEET_WATCH_OUTBOX_DIR", "/var/lib/brain/whatsapp-observer/outbox"))
    files = sorted(outbox.glob("*.json"))
    if not files:
        print("fila vazia: nenhum evento preso")
        return 0

    conn = ro_connect(Path("/var/lib/brain/runtime/brain-runtime.db"))
    if conn is None:
        print("ERRO: brain-runtime.db ilegivel", file=sys.stderr)
        return 1
    ausentes = 0
    try:
        for f in files:
            try:
                ev = json.loads(f.read_text())["event"]
            except Exception as e:
                print(f"ILEGIVEL  {f.name}: {type(e).__name__}")
                ausentes += 1
                continue
            n = conn.execute(
                "SELECT COUNT(*) FROM transport_events WHERE event_id = ?",
                (ev["event_id"],),
            ).fetchone()[0]
            idade = (now() - json.loads(f.read_text()).get("spooled_at", now())) / 3600
            if not n:
                ausentes += 1
            print(f"{'JA SALVO ' if n else 'AUSENTE  '} {ev['event_id'][:28]}… "
                  f"kind={ev.get('transport_kind')} ha={idade:.1f}h")
    finally:
        conn.close()

    print()
    if ausentes:
        print(f"{ausentes} de {len(files)} AUSENTES no Brain: ha risco de perda, "
              "e a fila esta de fato presa.")
    else:
        print(f"Todos os {len(files)} eventos ja estao no Brain: sao duplicatas, "
              "nao ha perda de dado. A fila esta mal varrida, nao entupida.")
    return 0


def group_for_investigation(to_alert: list[dict]) -> list[dict]:
    """Um incidente costuma levantar varios achados na mesma area.

    `spawn_failed` e `gave_up` sao o mesmo evento visto de dois angulos -- os
    mesmos cartoes, a mesma causa. Acordar um agente para cada um gastava duas
    vagas da cota horaria e devolvia duas mensagens quase iguais. Investiga-se
    o mais severo de cada area, com os irmaos anexados como contexto; todas as
    assinaturas do grupo sao marcadas como feitas, senao a sobra viraria uma
    segunda investigacao na rodada seguinte.
    """
    ordem = {"critical": 0, "error": 1, "warning": 2}
    por_area: dict[str, list[dict]] = {}
    for f in to_alert:
        por_area.setdefault(f["area"], []).append(f)

    escolhidos = []
    for achados in por_area.values():
        achados.sort(key=lambda f: ordem.get(f["severity"], 9))
        principal = dict(achados[0])
        principal["_group_sigs"] = [f["sig"] for f in achados]
        if len(achados) > 1:
            principal["related"] = [f["message"] for f in achados[1:]]
        escolhidos.append(principal)
    return escolhidos


def alert_batches(findings, header):
    """Bound by Telegram's UTF-16 limit, keeping each incident with its receipt."""
    batch, size = [], len(header.encode("utf-16-le")) // 2
    for f in findings:
        line = f"[{f['severity'].upper()}] {f['area']}: {f['message']}"
        # External-looking fields from legacy probes cannot grow an alert without bound.
        line = line.encode("utf-16-le")[:5000].decode("utf-16-le", "ignore")
        cost = len(line.encode("utf-16-le")) // 2 + 1
        if batch and size + cost > 3800:
            yield batch, header + "\n" + "\n".join(item[1] for item in batch)
            batch, size = [], len(header.encode("utf-16-le")) // 2
        batch.append((f, line))
        size += cost
    if batch:
        yield batch, header + "\n" + "\n".join(item[1] for item in batch)


def run_alerting(findings: list[dict]) -> bool:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE_DIR / ".alert.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run_alerting_locked(findings)


def _run_alerting_locked(findings: list[dict]) -> bool:
    streaks = load_state("streaks.json")
    alerted = load_state("alerted.json")
    current = {f["sig"]: f for f in findings if not f.get("report_only")}
    new_streaks = {sig: streaks.get(sig, 0) + 1 for sig in current}
    to_alert = [current[sig] for sig, n in new_streaks.items()
                if n >= (1 if current[sig].get("immediate") else FAILURE_STREAK)
                and sig not in alerted]
    unavailable = any(f.get("detection_unavailable") for f in findings)
    recovered = [sig for sig in alerted if sig not in current
                 and not (unavailable and sig.startswith("atendimento:"))]
    pending = load_state("pending.json")
    # Persist BEFORE sending: a transient fault must remain reportable even if it clears.
    for item in to_alert:
        pending.setdefault(item["sig"], item)
    for sig in list(pending):
        if sig in alerted:
            pending.pop(sig)  # receipt committed before a crash updating the pending file
    save_state("pending.json", pending)
    to_send = []
    for sig, item in pending.items():
        item = dict(item)
        if sig not in current:
            suffix = ("Estado atual não verificável." if unavailable else
                      "Sinal não observado nesta rodada; ocorrência anterior ainda precisava ser comunicada.")
            item["message"] += " " + suffix
        to_send.append(item)
    successful, delivery_ok = [], True
    for batch, text in alert_batches(to_send, "⚠️ Frota Hermes — incidentes para acompanhamento"):
        if send_telegram(text):
            for f, _ in batch:
                alerted[f["sig"]] = datetime.now(timezone.utc).isoformat()
                successful.append(f)
            save_state("alerted.json", alerted)
            for f, _ in batch:
                pending.pop(f["sig"], None)
            save_state("pending.json", pending)
        else:
            delivery_ok = False
    cleared = [{"sig":sig,"area":"acompanhamento","severity":"info",
                "message":f"{sig}: sinal deixou de ser observado. Renato deve confirmar resolução "
                          "e necessidade de retomar o atendimento; isso não comprova resposta ao lead."}
               for sig in recovered]
    for batch, text in alert_batches(cleared, "ℹ️ Frota Hermes — mudança de estado"):
        if send_telegram(text):
            for f, _ in batch:
                alerted.pop(f["sig"], None)
            save_state("alerted.json", alerted)
        else:
            delivery_ok = False
    # Diagnosis cannot block detection, and remains bounded by the existing hourly budget.
    if successful:
        investigations = load_state("investigations.json")
        feitas = investigations.setdefault("done", {})
        agora = datetime.now(timezone.utc).isoformat()
        for item in group_for_investigation(successful):
            group = item.pop("_group_sigs", [item["sig"]])
            if all(sig in feitas for sig in group):
                continue
            if investigation_slots_left(investigations) <= 0:
                break  # operator already has the actionable alert
            if request_investigation(item):
                for sig in group:
                    feitas[sig] = agora
                investigations.setdefault("recent", []).append(now())
        save_state("investigations.json", investigations)
    save_state("streaks.json", new_streaks)
    save_state("alerted.json", alerted)
    return delivery_ok


# ---------------------------------------------------------------- main

REPORT_PATH = Path(os.environ.get(
    "FLEET_WATCH_REPORT", "/var/log/hermes-fleet-watch/report.jsonl"))


def main() -> int:
    if "--investigate" in sys.argv:
        return run_investigation(sys.argv[sys.argv.index("--investigate") + 1])
    if "--check-ingested" in sys.argv:
        return run_check_ingested()

    started = now()
    findings: list[dict] = []
    raw: dict = {}

    steps = [
        ("systemd", check_units),
        ("kanban", check_kanban),
        ("atendimento", lambda: detect_attendance(HERMES_ROOT, now())),
        ("filas", check_queues),
        ("brain", check_brain_runtime),
        ("gateway", check_gateway_heartbeats),
        ("gateway_exits", check_unclean_exits),
        ("logs", check_errors_log),
        ("integridade", check_integrity),
    ]
    if "--fast" not in sys.argv:
        steps.append(("cron", check_cron_doctor))

    for name, fn in steps:
        try:
            findings.extend(fn())
        except Exception as e:
            # Um probe quebrado nunca derruba o vigia -- mas fica visivel.
            findings.append(finding("warning", "watchdog",
                                    f"probe '{name}' falhou: {type(e).__name__}: {e}",
                                    key=f"probe_{name}"))
    try:
        hf, raw = check_health()
        findings.extend(hf)
    except Exception as e:
        findings.append(finding("warning", "watchdog",
                                f"probe 'health' falhou: {type(e).__name__}",
                                key="probe_health"))

    order = {"critical": 0, "error": 1, "warning": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 9))

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((now() - started) * 1000),
        "counts": {
            sev: sum(1 for f in findings if f["severity"] == sev)
            for sev in ("critical", "error", "warning")
        },
        "findings": findings,
        "health_raw": raw,
    }

    if "--alert" in sys.argv:
        try:
            REPORT_PATH.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            with REPORT_PATH.open("a") as fh:
                fh.write(json.dumps(report, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"aviso: relatorio nao gravado: {e}", file=sys.stderr)
        delivered = run_alerting(findings)
        # Em modo timer, achado NAO e falha do servico: ele sai por Telegram e
        # pelo relatorio. Exit != 0 fica reservado para o vigia ter quebrado --
        # so assim `systemctl status` distingue "achou problema" de "eu quebrei".
        return 0 if delivered else 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
