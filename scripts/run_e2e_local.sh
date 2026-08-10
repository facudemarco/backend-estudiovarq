#!/usr/bin/env bash
# =============================================================================
# Prueba end-to-end LOCAL del CRM EstudioVArq (n8n + backend + MySQL + túnel).
#
# Qué hace, en orden:
#   1. Verifica/levanta el backend uvicorn en :8000 (si no corre ya).
#   2. Verifica/levanta el túnel cloudflared hacia :8000 (si no hay túnel vivo)
#      y detecta la URL actual. El binario se descarga solo si falta.
#   3. Re-publica los 5 workflows n8n apuntando al backend via la URL del túnel:
#      Entrada, ReplyHandler, Seguimientos (con shape-fix idempotente),
#      WarmingAgent y Calendario (calendario no depende del túnel, se re-pública
#      por consistencia). Usa los builders (env BACKEND_URL).
#   4. Corre la suite pytest local.
#   5. Corre el gate e2e (gate_phase2.py) — el check 13 de seguimientos solo
#      pasa en ventana laboral Lun-Vie 08-18 ARG.
#
# Uso:
#   scripts/run_e2e_local.sh            # todo: backend+túnel+publish+tests+gate
#   scripts/run_e2e_local.sh --no-gate  # salta el gate (fuera de ventana, etc.)
#   scripts/run_e2e_local.sh --publish-only  # solo re-publica los workflows
#
# Requisitos: venv/ (python), .env (credenciales), acceso a n8n.iwebtecnology.com
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/venv"
PY="$VENV/bin/python"
PORT="${BACKEND_PORT:-8000}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-$ROOT/scripts/bin/cloudflared}"
TUNNEL_LOG="$ROOT/scripts/.tunnel.log"
TUNNEL_URL_FILE="$ROOT/scripts/.tunnel_url"
GATE="$ROOT/scripts/gate_phase2.py"

DO_GATE=1
DO_PUBLISH=1
[ "${1:-}" = "--no-gate" ] && DO_GATE=0
[ "${1:-}" = "--publish-only" ] && { DO_GATE=0; DO_PUBLISH=1; }

say() { echo -e "\n\033[1;36m==> $*\033[0m" >&2; }
die() { echo -e "\033[1;31mERROR: $*\033[0m" >&2; exit 1; }

[ -x "$PY" ] || die "venv no encontrado en $VENV (crea el venv primero)"
[ -f "$ROOT/.env" ] || die "falta .env en $ROOT"

cd "$ROOT" || die "no pude entrar a $ROOT"

# ---------------------------------------------------------------------------
# 1. Backend
# ---------------------------------------------------------------------------
start_backend() {
  if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/crm/status"; then
    say "backend ya corriendo en :$PORT"
    return 0
  fi
  say "levantando backend uvicorn en :$PORT (log: /tmp/opencode/backend_e2e.log)"
  mkdir -p /tmp/opencode
  "$PY" - <<'EOF' || die "no pude levantar uvicorn"
import subprocess, os, sys
log = open("/tmp/opencode/backend_e2e.log", "wb")
p = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", os.environ.get("BACKEND_PORT", "8000")],
    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    cwd=".")
print("uvicorn pid:", p.pid)
EOF
  for i in $(seq 1 15); do
    curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/crm/status" && return 0
    sleep 1
  done
  die "backend no respondió en :$PORT (ver /tmp/opencode/backend_e2e.log)"
}

# ---------------------------------------------------------------------------
# 2. Túnel cloudflared
# ---------------------------------------------------------------------------
download_cloudflared() {
  mkdir -p "$(dirname "$CLOUDFLARED_BIN")"
  say "descargando cloudflared a $CLOUDFLARED_BIN"
  curl -sL --max-time 90 -o "$CLOUDFLARED_BIN" \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" \
    || die "falló la descarga de cloudflared"
  chmod +x "$CLOUDFLARED_BIN"
}

get_tunnel_url() {
  if [ -f "$TUNNEL_URL_FILE" ]; then
    local url
    url="$(cat "$TUNNEL_URL_FILE" 2>/dev/null)"
    if [ -n "$url" ] && curl -s -o /dev/null --max-time 5 "$url/crm/status"; then
      echo "$url"
      return 0
    fi
  fi
  return 1
}

start_tunnel() {
  local url
  if url="$(get_tunnel_url)"; then
    say "túnel vivo: $url"
    echo "$url" > "$TUNNEL_URL_FILE"
    echo "$url"
    return 0
  fi
  [ -x "$CLOUDFLARED_BIN" ] || download_cloudflared
  say "levantando túnel cloudflared -> http://127.0.0.1:$PORT (log: $TUNNEL_LOG)"
  : > "$TUNNEL_LOG"
  "$PY" - >/dev/null 2>&1 <<EOF || die "no pude levantar cloudflared"
import subprocess
log = open("$TUNNEL_LOG", "wb")
p = subprocess.Popen(
    ["$CLOUDFLARED_BIN", "tunnel", "--url", "http://127.0.0.1:$PORT", "--no-autoupdate"],
    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print("cloudflared pid:", p.pid)
EOF
  for i in $(seq 1 60); do
    sleep 2
    url="$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)"
    if [ -n "$url" ] && curl -s -o /dev/null --max-time 8 "$url/crm/status"; then
      echo "$url" > "$TUNNEL_URL_FILE"
      say "túnel listo: $url"
      echo "$url"
      return 0
    fi
  done
  die "túnel no levantó (ver $TUNNEL_LOG)"
}

# ---------------------------------------------------------------------------
# 3. Re-publicar workflows
# ---------------------------------------------------------------------------
republish() {
  say "re-publicando workflows con BACKEND_URL=$BACKEND_URL"
  local ok=1
  for wf in entrada reply warming seguimientos; do
    say "  -> n8n_$wf.py"
    BACKEND_URL="$BACKEND_URL" "$PY" "scripts/n8n_$wf.py" || { echo "FALLO n8n_$wf"; ok=0; }
  done
  say "  -> n8n_calendario.py (no depende del túnel)"
  BACKEND_URL="$BACKEND_URL" "$PY" "scripts/n8n_calendario.py" || { echo "FALLO n8n_calendario"; ok=0; }
  [ "$ok" = 1 ] || die "alguno de los builders falló (revisar arriba)"
}

# ---------------------------------------------------------------------------
# 4. Suite pytest
# ---------------------------------------------------------------------------
run_tests() {
  say "corriendo suite pytest"
  if ! "$VENV/bin/pytest" -q 2>&1 | tee /tmp/opencode/pytest_e2e.log; then
    if grep -aq "1226\|max_connections_per_hour" /tmp/opencode/pytest_e2e.log; then
      die "la suite falló por CUOTA MariaDB (1226 max_connections_per_hour=500). Es ambiental: esperá el reset horario (~top of next hour) y reintentá. Código sano: última corrida verde fue 62 passed."
    fi
    die "la suite pytest tiene fallos (ver /tmp/opencode/pytest_e2e.log)"
  fi
}

# ---------------------------------------------------------------------------
# 5. Gate e2e
# ---------------------------------------------------------------------------
run_gate() {
  say "corriendo gate e2e (gate_phase2.py)"
  "$PY" -u "$GATE" | tee /tmp/opencode/gate2_run.log || die "el gate reportó fallos"
}

# ---------------------------------------------------------------------------
main() {
  start_backend
  local url
  url="$(start_tunnel)"
  BACKEND_URL="$url"
  export BACKEND_URL

  if [ "$DO_PUBLISH" = 1 ]; then
    republish
  else
    say "publicación omitida (--no-publish)"
  fi

  run_tests

  if [ "$DO_GATE" = 1 ]; then
    run_gate
  else
    say "gate omitido (--no-gate); pendiente correr en ventana laboral Lun-Vie 08-18 ARG"
  fi

  say "E2E local completo. Resumen:"
  echo "  backend    : http://127.0.0.1:$PORT"
  echo "  túnel      : $BACKEND_URL"
  echo "  (guardado en $TUNNEL_URL_FILE — se reusa si sigue vivo)"
}

main
