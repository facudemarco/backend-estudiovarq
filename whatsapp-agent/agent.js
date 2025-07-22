global.crypto = require('node:crypto');
const express = require('express');
const makeWASocket = require('@whiskeysockets/baileys').default;
const { useMultiFileAuthState } = require('@whiskeysockets/baileys');

const app = express();
app.use(express.json());

let sock;

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth'); // ✅ Ahora dentro de una función async
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
  });

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect } = update;
    if (connection === 'close') {
      const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== 401;
      console.log("❌ Conexión cerrada. Reintentando:", shouldReconnect);
      if (shouldReconnect) startSock();
    } else if (connection === 'open') {
      console.log("✅ Conectado a WhatsApp");
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
    console.error(err);
    res.status(500).json({ error: err.toString() });
  }
});

startSock(); // ✅ Disparás la función que contiene el await

app.listen(3008, () => console.log("📡 Agent escuchando en puerto 3008"));
