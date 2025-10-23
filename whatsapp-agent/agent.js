/* whatsapp-agent/agent.js */
global.crypto = require('node:crypto');
const express = require('express');
const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const fs = require('fs');

const N8N_REPLIES_URL    = process.env.N8N_REPLIES_URL    || 'https://n8n.iwebtecnology.com/webhook/estudiovarq-replies';
const N8N_REPLIES_SECRET = process.env.N8N_REPLIES_SECRET || 'MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq';

const app = express();
app.use(express.json());

const logger = pino({
  level: 'silent',
  transport: { target: 'pino-pretty', options: { colorize: true, ignore: 'pid,hostname,time' } },
});

let sock;
let reconnectEnabled = true;
let lastQRTime = 0;
let isAuthenticated = false;
let starting = false; // evita múltiples startSock en paralelo

function normalizeE164Plus(x) {
  const digits = String(x || '').replace(/[^\d]/g, '');
  return digits ? `+${digits}` : '';
}

function extractText(msg) {
  const m = msg?.message || {};
  if (m.ephemeralMessage?.message)           return extractText({ message: m.ephemeralMessage.message });
  if (m.viewOnceMessage?.message)            return extractText({ message: m.viewOnceMessage.message });
  if (m.viewOnceMessageV2?.message)          return extractText({ message: m.viewOnceMessageV2.message });
  if (m.documentWithCaptionMessage?.message) return extractText({ message: m.documentWithCaptionMessage.message });
  const txt =
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    m.templateButtonReplyMessage?.selectedId ||
    '';
  const hasMedia = !!(m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage);
  return txt && txt.trim() ? txt.trim() : (hasMedia ? '[media]' : '');
}

async function startSock() {
  if (starting) return;
  starting = true;

  // Auth folder
  if (!fs.existsSync('./auth')) {
    fs.mkdirSync('./auth', { recursive: true });
    console.log('📁 Carpeta ./auth creada para nuevas credenciales');
  }
  const { state, saveCreds } = await useMultiFileAuthState('./auth');

  // *** clave: negociar versión correcta del WhatsApp Web ***
  const { version, isLatest } = await fetchLatestBaileysVersion();
  console.log('🧩 WA Web version:', version, isLatest ? '(latest)' : '(fallback)');

  sock = makeWASocket({
    version,                     // 👈 importante para evitar 405
    auth: state,
    logger,
    // Usar un browser Desktop estándar
    browser: ['Desktop', 'Chrome', '121.0.0'],
    markOnlineOnConnect: false,
    syncFullHistory: false,
    // NO usar printQRInTerminal (deprecado) — manejamos QR en connection.update
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    // Mostrar QR (con rate limit simple)
    if (qr && !isAuthenticated) {
      const now = Date.now();
      if (now - lastQRTime > 20000) {
        console.log('🟢 Escaneá este QR con WhatsApp (Dispositivos vinculados):');
        qrcode.generate(qr, { small: true });
        lastQRTime = now;
      }
    }

    if (connection === 'close') {
      const statusCode =
        lastDisconnect?.error?.output?.statusCode ??
        lastDisconnect?.error?.statusCode ??
        lastDisconnect?.error?.code ?? 'desconocido';

      console.log(`❌ Conexión cerrada (Código: ${statusCode})`);
      isAuthenticated = false;

      // 405 / badSession / 401 ⇒ reseteo duro de credenciales
      const hardResetCodes = new Set([DisconnectReason.badSession, 405, 401]);
      if (hardResetCodes.has(statusCode)) {
        try {
          fs.rmSync('./auth', { recursive: true, force: true });
          console.log('🧹 Sesión borrada. Se generará un nuevo QR…');
        } catch {}
        starting = false;
        setTimeout(startSock, 1500);
        return;
      }

      if (statusCode === DisconnectReason.loggedOut) {
        console.log('⚠️ Sesión cerrada por el usuario. Esperando nuevo arranque para QR.');
        reconnectEnabled = false;
        starting = false;
        return;
      }

      if (reconnectEnabled) {
        starting = false;
        console.log('🔄 Reintentando en 5s…');
        setTimeout(startSock, 5000);
      } else {
        starting = false;
      }
    } else if (connection === 'open') {
      console.log('✅ Autenticado correctamente');
      isAuthenticated = true;
      lastQRTime = 0;
      starting = false;
    } else if (connection === 'connecting') {
      console.log('🔄 Conectando...');
    }
  });

  // Inbound messages → n8n
  sock.ev.on('messages.upsert', async (evt) => {
    try {
      if (evt.type !== 'notify') return;
      for (const msg of evt.messages || []) {
        if (msg.key.fromMe) continue;
        const jid = msg.key.remoteJid || '';
        if (jid.includes('-') && jid.endsWith('@g.us')) continue;
        const phone = normalizeE164Plus(jid.split('@')[0] || '');
        const text  = extractText(msg);
        if (!phone) continue;

        console.log('[inbound]', { phone, text });

        try {
          const resp = await fetch(N8N_REPLIES_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Secret': N8N_REPLIES_SECRET },
            body: JSON.stringify({ phone, text })
          });
          const body = await resp.text();
          console.log(`[agent→n8n] ${resp.status} ${body}`);
        } catch (fetchError) {
          console.error('Error enviando a N8N:', fetchError);
        }
      }
    } catch (e) {
      console.error('messages.upsert error:', e);
    }
  });
}

app.post('/send', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) return res.status(400).json({ error: 'phone y message son requeridos' });
  if (!sock || !isAuthenticated) return res.status(503).json({ error: 'WhatsApp no conectado o no autenticado' });

  try {
    const digits = String(phone).replace(/\D/g, '');
    if (!digits) return res.status(400).json({ error: 'Número de teléfono inválido' });
    await sock.sendMessage(`${digits}@s.whatsapp.net`, { text: message });
    console.log(`[outbound] Enviado a ${phone}: ${message}`);
    res.json({ status: 'sent', phone: `+${digits}` });
  } catch (err) {
    console.error('Error enviando mensaje:', err);
    res.status(500).json({ error: err.toString() });
  }
});

app.get('/status', (req, res) => {
  res.json({ connected: !!sock && isAuthenticated, authenticated: isAuthenticated, timestamp: new Date().toISOString() });
});

process.on('SIGINT', () => {
  console.log('🛑 Cerrando agente…');
  reconnectEnabled = false;
  if (sock) sock.end();
  process.exit(0);
});
process.on('SIGTERM', () => {
  console.log('🛑 Terminando agente…');
  reconnectEnabled = false;
  if (sock) sock.end();
  process.exit(0);
});

startSock();
app.listen(3008, '0.0.0.0', () => {
  console.log('📡 Agent escuchando en puerto 3008');
  console.log('📱 Endpoints: POST /send | GET /status');
});
