global.crypto = require('node:crypto');
const express = require('express');
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino'); // Importar pino

const app = express();
app.use(express.json());

// Configurar logger de Pino
const logger = pino({
  level: 'silent', // Puedes cambiar a 'info' para depuración
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
      ignore: 'pid,hostname,time' // Simplifica los logs
    }
  }
});

let sock;
let reconnectEnabled = true;

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth');
  
  sock = makeWASocket({
    auth: state,
    logger: logger, // Usar la instancia de Pino configurada
    browser: ['Ubuntu', 'Chrome', '122.0.0'],
    shouldIgnoreJid: () => true, // Reduce carga
    syncFullHistory: false, // Mejora rendimiento
    phone: {
      code: false,
      number: null
    }
  });

  sock.ev.on('creds.update', saveCreds);
  
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    // Manejar QR manualmente
    if (qr) {
      const qrcode = require('qrcode-terminal');
      console.log("🟢 ESCANEA ESTE CÓDIGO QR CON WHATSAPP:");
      qrcode.generate(qr, { small: true });
    }
    
    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      
      console.log(`❌ Conexión cerrada (Código: ${statusCode || 'desconocido'})`);
      
      if (shouldReconnect && reconnectEnabled) {
        console.log("🔄 Reconectando en 5 segundos...");
        setTimeout(startSock, 5000);
      }
    } else if (connection === 'open') {
      console.log("✅ Autenticado correctamente");
    }
  });
}

app.post('/send', async (req, res) => {
  const { phone, message } = req.body;
  if (!sock) return res.status(503).json({ error: 'WhatsApp no conectado' });
  try {
    await sock.sendMessage(`${phone}@s.whatsapp.net`, { text: message });
    res.json({ status: 'sent' });
  } catch (err) {
    logger.error(err); // Usar el logger configurado
    res.status(500).json({ error: err.toString() });
  }
});

startSock();

app.listen(3008, '0.0.0.0', () => console.log("📡 Agent escuchando en puerto 3008"));