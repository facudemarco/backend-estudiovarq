/* whatsapp-agent/agent.js */
global.crypto = require('node:crypto');
const express = require('express');
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const path = require('path');

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
let lastQRTime = 0; // Control para evitar QR en loop
let isAuthenticated = false; // Estado de autenticación

function normalizeE164Plus(x) {
  const digits = String(x || '').replace(/[^\d]/g, '');
  return digits ? `+${digits}` : '';
}

// Extrae texto/caption de cualquier tipo de mensaje (desenvuelve contenedores)
function extractText(msg) {
  const m = msg?.message || {};
  if (m.ephemeralMessage?.message)          return extractText({ message: m.ephemeralMessage.message });
  if (m.viewOnceMessage?.message)           return extractText({ message: m.viewOnceMessage.message });
  if (m.viewOnceMessageV2?.message)         return extractText({ message: m.viewOnceMessageV2.message });
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
  const AUTH_DIR = path.resolve(__dirname, 'auth');
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  const fs = require('fs');

  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    console.log('📁 Carpeta ./auth creada para nuevas credenciales');
  }

  sock = makeWASocket({
    auth: state,
    logger,
    browser: ['Ubuntu', 'Chrome', '122.0.0'],
    shouldIgnoreJid: () => false,
    syncFullHistory: false,
    phone: { code: false, number: null },
    printQRInTerminal: true, // Deshabilitado para control manual
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    // Control del QR - solo mostrar si han pasado al menos 30 segundos
    if (qr && !isAuthenticated) {
      const now = Date.now();
      if (now - lastQRTime > 30000) { // 30 segundos de intervalo mínimo
        console.log('🟢 ESCANEA ESTE CÓDIGO QR CON WHATSAPP:');
        qrcode.generate(qr, { small: true });
        lastQRTime = now;
        console.log('⏱️ Si el QR expira, se generará uno nuevo en 30 segundos...');
      }
    }
    
    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      
      console.log(`❌ Conexión cerrada (Código: ${statusCode || 'desconocido'})`);
      
      // Reset del estado de autenticación si se desconecta
      isAuthenticated = false;
      
      if (statusCode === DisconnectReason.loggedOut) {
        console.log('⚠️ Sesión cerrada por el usuario. Se requiere nuevo QR.');
        reconnectEnabled = false; // Detener reconexión automática
        return;
      }
      
      if (statusCode === DisconnectReason.badSession || statusCode === 405) {
        console.log('⚠️ Sesión corrupta detectada, eliminando y regenerando...');
        const fs = require('fs');
        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        console.log('🧹 Carpeta ./auth eliminada, se generará un nuevo QR');
        startSock();
        return;
      }

      if (shouldReconnect && reconnectEnabled) {
        console.log('🔄 Reconectando en 5 segundos…');
        setTimeout(() => {
          if (reconnectEnabled) startSock();
        }, 5000);
      }
    } else if (connection === 'open') {
      console.log('✅ Autenticado correctamente');
      isAuthenticated = true;
      lastQRTime = 0; // Reset del control de QR
    } else if (connection === 'connecting') {
      console.log('🔄 Conectando...');
    }
  });

  sock.ev.on('messages.upsert', async (evt) => {
    try {
      if (evt.type !== 'notify') return;

      for (const msg of evt.messages || []) {
        if (msg.key.fromMe) continue;  // ignora tus propios mensajes

        const jid = msg.key.remoteJid || '';
        if (jid.includes('-') && jid.endsWith('@g.us')) continue; // opcional: ignorar grupos

        const phone = normalizeE164Plus(jid.split('@')[0] || '');
        const text  = extractText(msg);
        if (!phone) continue;

        console.log('[inbound]', { phone, text });

        try {
          const resp = await fetch(N8N_REPLIES_URL, {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json', 
              'X-Secret': N8N_REPLIES_SECRET 
            },
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

// Endpoint para enviar mensajes salientes
app.post('/send', async (req, res) => {
  const { phone, message } = req.body;
  
  if (!phone || !message) {
    return res.status(400).json({ error: 'phone y message son requeridos' });
  }
  
  if (!sock || !isAuthenticated) {
    return res.status(503).json({ error: 'WhatsApp no conectado o no autenticado' });
  }
  
  try {
    const digits = String(phone).replace(/\D/g, '');
    if (!digits) {
      return res.status(400).json({ error: 'Número de teléfono inválido' });
    }
    
    await sock.sendMessage(`${digits}@s.whatsapp.net`, { text: message });
    console.log(`[outbound] Enviado a ${phone}: ${message}`);
    res.json({ status: 'sent', phone: `+${digits}` });
  } catch (err) {
    console.error('Error enviando mensaje:', err);
    res.status(500).json({ error: err.toString() });
  }
});

// Endpoint de estado
app.get('/status', (req, res) => {
  res.json({
    connected: !!sock && isAuthenticated,
    authenticated: isAuthenticated,
    timestamp: new Date().toISOString()
  });
});

// Manejo limpio de cierre
process.on('SIGINT', () => {
  console.log('🛑 Cerrando agente...');
  reconnectEnabled = false;
  if (sock) {
    sock.end();
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('🛑 Terminando agente...');
  reconnectEnabled = false;
  if (sock) {
    sock.end();
  }
  process.exit(0);
});

startSock();
app.listen(3008, '0.0.0.0', () => {
  console.log('📡 Agent escuchando en puerto 3008');
  console.log('📱 Endpoints disponibles:');
  console.log('   POST /send - Enviar mensajes');
  console.log('   GET /status - Estado de conexión');
});