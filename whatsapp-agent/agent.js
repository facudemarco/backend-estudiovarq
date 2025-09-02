/* whatsapp-agent/agent.js */
global.crypto = require('node:crypto');
const express = require('express');
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const fetch = require('node-fetch');
const qrcode = require('qrcode-terminal');

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

function normalizeE164Plus(x) {
  const digits = String(x || '').replace(/[^\d]/g, '');
  return digits ? `+${digits}` : '';
}

// --- Extrae texto de forma robusta (desenvuelve mensajes) ---
function extractText(msg) {
  const m = msg?.message || {};
  // Recursivo: unwrap contenedores
  if (m.ephemeralMessage?.message) return extractText({ message: m.ephemeralMessage.message });
  if (m.viewOnceMessage?.message)  return extractText({ message: m.viewOnceMessage.message });
  if (m.viewOnceMessageV2?.message) return extractText({ message: m.viewOnceMessageV2.message });
  if (m.documentWithCaptionMessage?.message) return extractText({ message: m.documentWithCaptionMessage.message });

  // Texto / captions / respuestas de botones/listas
  const txt =
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    m.templateButtonReplyMessage?.selectedId ||
    '';

  // Si no hay texto pero hay media, marcamos como "[media]"
  const hasMedia = !!(m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage);
  return txt && txt.trim().length ? txt.trim() : (hasMedia ? '[media]' : '');
}

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth');

  sock = makeWASocket({
    auth: state,
    logger,
    browser: ['Ubuntu', 'Chrome', '122.0.0'],
    shouldIgnoreJid: () => false,        // << NO ignorar entrantes
    syncFullHistory: false,
    phone: { code: false, number: null },
    printQRInTerminal: false,
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

  // ÚNICO listener de replies
  sock.ev.on('messages.upsert', async (evt) => {
    try {
      if (evt.type !== 'notify') return;

      for (const msg of evt.messages || []) {
        if (msg.key.fromMe) continue;                    // ignorá lo que vos mismo enviaste

        const jid = msg.key.remoteJid || '';
        // Ignorar grupos (si no los querés procesar)
        if (jid.includes('-') && jid.endsWith('@g.us')) continue;

        const phone = normalizeE164Plus(jid.split('@')[0] || '');
        const text  = extractText(msg);

        // Si igual no logramos extraer nada, lo consideramos vacío
        if (!phone) continue;
        if (!text) {
          // Igual reenviamos para marcar last_reply_at (sin texto)
          console.log(`[agent] inbound from ${phone} (empty text)`);
        } else {
          console.log(`[agent] inbound from ${phone}: "${text}"`);
        }

        // Post directo a n8n (webhook replies)
        try {
          const resp = await fetch(N8N_REPLIES_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Secret': N8N_REPLIES_SECRET },
            body: JSON.stringify({ phone, text })
          });
          const body = await resp.text();
          console.log(`[agent→n8n] ${resp.status} ${body}`);
        } catch (e) {
          console.error('agent→n8n fetch error:', e);
        }
      }
    } catch (e) {
      console.error('messages.upsert handler error:', e);
    }
  });
}

// Endpoint para enviar mensajes salientes
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