#!/usr/bin/env bash
# =============================================================================
# Deploy a PRODUCCIÓN: re-publica los 5 workflows n8n apuntando al backend de
# producción (URL real, NO el túnel trycloudflare local).
#
# Uso:
#   BACKEND_URL="https://backend-prod.estudiovarq.com" scripts/deploy_workflows.sh
#
# Si no pasás BACKEND_URL, intenta leerla de .env (BACKEND_PROD_URL) y aborta si
# no existe (así no se hierarchy-la un túnel local a producción por accidente).
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/venv/bin/python"

say() { echo -e "\n\033[1;36m==> $*\033[0m" >&2; }
die() { echo -e "\033[1;31mERROR: $*\033[0m" >&2; exit 1; }

[ -x "$PY" ] || die "venv no encontrado"
cd "$ROOT" || die "no pude entrar a $ROOT"

BACKEND_URL="${BACKEND_URL:-}"
if [ -z "$BACKEND_URL" ]; then
  if [ -f "$ROOT/.env" ]; then
    BACKEND_URL="$(grep -P '^BACKEND_PROD_URL=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"' || true)"
  fi
fi
if [ -z "$BACKEND_URL" ]; then
  die "BACKEND_URL requerido. Ej: BACKEND_URL=https://crm.estudiovarq.com scripts/deploy_workflows.sh\n  (o definí BACKEND_PROD_URL=... en .env)."
fi
if echo "$BACKEND_URL" | grep -q 'trycloudflare.com'; then
  die "BACKEND_URL apunta a un túnel trycloudflare ($BACKEND_URL). Esto es DEPLOY A PRODUCCIÓN: usá la URL estable, no un quick tunnel."
fi

export BACKEND_URL
say "backends URL de producción: $BACKEND_URL"
say "verificando que el backend de producción responde..."
if ! curl -s -o /dev/null --max-time 10 "$BACKEND_URL/crm/status"; then
  die "no se pudo alcanzar $BACKEND_URL/crm/status — aborto el deploy"
fi

if [ "${1:-}" = "--dry-run" ]; then
  say "DRY-RUN: no se publica nada. BACKEND_URL=$BACKEND_URL"
  exit 0
fi

ok=1
for wf in entrada reply warming seguimientos; do
  say "  -> n8n_$wf.py"
  BACKEND_URL="$BACKEND_URL" "$PY" "scripts/n8n_$wf.py" || { echo "FALLO n8n_$wf" >&2; ok=0; }
done
say "  -> n8n_calendario.py (GCal directo, no usa BACKEND)"
BACKEND_URL="$BACKEND_URL" "$PY" "scripts/n8n_calendario.py" || { echo "FALLO n8n_calendario" >&2; ok=0; }

if [ "$ok" = 1 ]; then
  say "Deploy OK. Workflows publicados apuntando a $BACKEND_URL"
else
  die "Hubo fallos en el deploy (revisar arriba)"
  exit 1
fi