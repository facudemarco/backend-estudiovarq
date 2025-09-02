/* whatsapp-agent/agent.js */
global.crypto = require('node:crypto');
const express = require('express');
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const fetch = require('node-fetch');
const qrcode = require('qrcode-terminal');

const BACKEND_WEBHOOK_URL = process.env.BACKEND_WEBHOOK_URL || 'http://127.0.0.1:8000/api/whatsapp-webhook';
const REPLIES_SECRET      = process.env.REPLIES_SECRET      || 'MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq';

const app = express();
app.use(express.json());

const logger = pino({
  level: 'silent',
  transport: { target: 'pino-pretty', options: { colorize: true, ignore: 'pid,hostname,time' } },
});

let sock;
let reconnectEnabled = true;

function normalizeE164Plus(jidOrPhone) {
  const digits = String(jidOrPhone).replace(/[^\d]/g, '');
  return `+${digits}`;
}

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth');

  sock = makeWASocket({
    auth: state,
    logger,
    browser: ['Ubuntu', 'Chrome', '122.0.0'],
    shouldIgnoreJid: () => false,
    syncFullHistory: false,
    phone: { code: false, number: null },
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log('🟢 ESCANEA ESTE CÓDIGO QR CON WHATSAPP:');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`❌ Conexión cerrada (Código: ${statusCode || 'desconocido'})`);
      if (shouldReconnect && reconnectEnabled) {
        console.log('🔄 Reconectando en 5 segundos…');
        setTimeout(startSock, 5000);
      }
    } else if (connection === 'open') {
      console.log('✅ Autenticado correctamente');
    }
  });

  // ÚNICO listener de replies (no duplicar)
  sock.ev.on('messages.upsert', async (m) => {
    try {
      if (m.type !== 'notify') return;
      for (const msg of m.messages || []) {
        if (msg.key.fromMe) continue;

        const jid = msg.key.remoteJid || '';
        const phone = normalizeE164Plus(jid.split('@')[0] || '');
        const text =
          msg.message?.conversation ||
          msg.message?.extendedTextMessage?.text ||
          msg.message?.imageMessage?.caption ||
          msg.message?.videoMessage?.caption ||
          '';

        if (!text) continue;

        const resp = await fetch(BACKEND_WEBHOOK_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Secret': REPLIES_SECRET },
          body: JSON.stringify({ from_: phone, text })
        });
        const body = await resp.text();
        console.log(`[agent→backend] ${resp.status} ${body}`);
      }
    } catch (e) {
      console.error('agent forward error:', e);
    }
  });
}

// Endpoint para enviar mensajes
app.post('/send', async (req, res) => {
  const { phone, message } = req.body;
  if (!sock) return res.status(503).json({ error: 'WhatsApp no conectado' });
  try {
    const digits = String(phone).replace(/\D/g, '');
    await sock.sendMessage(`${digits}@s.whatsapp.net`, { text: message });
    res.json({ status: 'sent' });
  } catch (err) {
    logger.error(err);
    res.status(500).json({ error: err.toString() });
  }
});

startSock();
app.listen(3008, '0.0.0.0', () => console.log('📡 Agent escuchando en puerto 3008'));