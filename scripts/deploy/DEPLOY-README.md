# Deploy del backend nuevo a producción (api-estudiovarq.iwebtecnology.com)

Subís vos el código manualmente (SFTP/scp/git). Pasos:

## 1) Subir y descomprimir
Subí `backend-estudiovarq-deploy.tar.gz` al server (ej: /root/) y:
```bash
mkdir -p /opt/api-estudiovarq
cd /opt/api-estudiovarq
tar xzf /root/backend-estudiovarq-deploy.tar.gz
```

## 2) Entorno y dependencias
```bash
cd /opt/api-estudiovarq
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

## 3) .env de producción
1. Si ya tenés un `.env` del backend viejo, usalo de base y **agregá/ajustá** (ver `.env.prod.template`):
   - `N8N_ENTRADA_URL="https://n8n.iwebtecnology.com/webhook/estudiovarq-entrada"`  ← URL REAL, no webhook-test
   - `CRM_SECRET="<el mismo que está en tu .env local>"` (coincide con la credencial n8n "EstudioVARq Secret")
   - `COOKIE_SECURE=true`
2. Si no tenés `.env`: copiá `.env.prod.template` a `.env` y completá las claves ocultas (PASSWORD, SENDER_PASSWORD, SECRET_KEY, SESSION_SECRET, CRM_SECRET, N8N_API_KEY).

## 4) Service systemd — backend
```bash
cp estudiovarq-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now estudiovarq-api
systemctl status estudiovarq-api   # ver que quede active (running)
```
> Ajustá `WorkingDirectory`/`EnvironmentFile`/`User` en la unit si la ruta real es otra.

## 6) Agente WhatsApp (Baileys) — mismo server
```bash
mkdir -p /opt/whatsapp-agent && cd /opt/whatsapp-agent
tar xzf /root/whatsapp-agent-deploy.tar.gz
npm install --omit=dev          # instala dependencias (baileys, express, ...)
cp /tmp/.../whatsapp-agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now whatsapp-agent
systemctl status whatsapp-agent   # active (running)
curl -s http://127.0.0.1:3008/health   # {"status":"ok"} = sesión viva
```
> El tar incluye `auth/` (la sesión escaneada ya) y `stopped.json`. El agente ya usa por
> default: `N8N_REPLIES_URL=https://n8n.iwebtecnology.com/webhook/estudiovarq-reply`,
> `CRM_INBOX_URL=http://localhost:8000/crm/inbox` y el puerto 3008. No hace falta configurar nada salvo que quieras otro puerto.

## 7) Verificar
```bash
curl -s http://127.0.0.1:8000/crm/status                  # backend en el server
curl -s https://api-estudiovarq.iwebtecnology.com/crm/status   # backend público
curl -s http://127.0.0.1:3008/health                      # agente WhatsApp
```
Debe responder **200** (o 401 si falta el header X-Secret — igual es señal de que está vivo).

## 8) Avisame cuando esté arriba
Con el backend y el agente 200 en producción corro los 5 workflows de n8n apuntando a
`https://api-estudiovarq.iwebtecnology.com` (deploy_workflows.sh).

---

### Notas
- El puerto 8000 ya lo usa el backend viejo en el proxy → verificá que el service viejo
  no esté escuchando en el mismo puerto (o usá otro puerto y actualizá el proxy npm).
- El front (web) ya apunta al api viejo; después de este deploy los endpoints web
  (formContact, houses) los responde el backend NUEVO (los incluye todos), así que no se rompe nada.
- El frontend Next.js apunta a `NEXT_PUBLIC_API_URL` — en producción debe quedar en
  `https://api-estudiovarq.iwebtecnology.com` (no localhost).