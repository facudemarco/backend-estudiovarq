global.crypto = require("node:crypto");
const express = require("express");
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const pino = require("pino");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(express.json());

const logger = pino({
  level: 'info', // o 'silent' si querés que baileys no hable nada
});

// --- CONFIG ---
const SESSION_NAME = "estudiovarq";
const AUTH_DIR = "./auth";
const AUTH_BACKUP_DIR = "./auth_backup";
const N8N_REPLIES_URL = process.env.N8N_REPLIES_URL || "https://n8n.iwebtecnology.com/webhook/estudiovarq-replies";
const N8N_REPLIES_SECRET = process.env.N8N_REPLIES_SECRET || "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq";

let sock;
let reconnectEnabled = true;
let isAuthenticated = false;
let lastQRTime = 0;
const QR_COOLDOWN_MS = 60000;

// --- HELPERS ---
function ensureDirs() {
  if (!fs.existsSync(AUTH_DIR)) fs.mkdirSync(AUTH_DIR, { recursive: true });
  if (!fs.existsSync(AUTH_BACKUP_DIR)) fs.mkdirSync(AUTH_BACKUP_DIR, { recursive: true });
}
function hasAuth() {
  return fs.existsSync(path.join(AUTH_DIR, "creds.json"));
}
function backupAuth() {
  try {
    if (hasAuth()) {
      fs.cpSync(AUTH_DIR, AUTH_BACKUP_DIR, { recursive: true });
    }
  } catch (e) {
    console.log("⚠️ Backup falló:", e.message);
  }
}
function restoreAuth() {
  if (!hasAuth() && fs.existsSync(path.join(AUTH_BACKUP_DIR, "creds.json"))) {
    console.log("♻️ Restaurando sesión desde backup...");
    fs.cpSync(AUTH_BACKUP_DIR, AUTH_DIR, { recursive: true });
  }
}
function normalizeE164Plus(x) {
  const digits = String(x || "").replace(/[^\d]/g, "");
  return digits ? `+${digits}` : "";
}
function extractText(msg) {
  const m = msg?.message || {};
  if (m.ephemeralMessage?.message) return extractText({ message: m.ephemeralMessage.message });
  if (m.viewOnceMessage?.message) return extractText({ message: m.viewOnceMessage.message });
  if (m.viewOnceMessageV2?.message) return extractText({ message: m.viewOnceMessageV2.message });
  if (m.documentWithCaptionMessage?.message) return extractText({ message: m.documentWithCaptionMessage.message });
  const txt =
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    m.templateButtonReplyMessage?.selectedId ||
    "";
  const hasMedia = !!(m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage);
  return txt && txt.trim() ? txt.trim() : hasMedia ? "[media]" : "";
}

// --- MAIN FUNCTION ---
async function startSock() {
  ensureDirs();
  restoreAuth();

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  sock = makeWASocket({
    auth: state,
    logger,
    browser: ["iWeb Agent", "Chrome", "1.0.0"],
    printQRInTerminal: false,
    syncFullHistory: false,
  });

  sock.ev.on("creds.update", (creds) => {
    saveCreds(creds);
    backupAuth();
  });

sock.ev.on("connection.update", (update) => {
  const { connection, lastDisconnect, qr } = update;

  // 🔳 BLOQUE QR: siempre mostrar 1 QR por evento, con anti-spam
  if (qr) {
    const now = Date.now();
    if (now - lastQRTime > QR_COOLDOWN_MS) {
      console.log("\n================================================");
      console.log("🟢 Escaneá este QR con WhatsApp (Estudio VARQ):");
      qrcode.generate(qr, { small: true });
      console.log("================================================");
      console.log(
        "ℹ️ Estado de la sesión:",
        isAuthenticated
          ? "YA AUTENTICADA (QR de cortesía, no hace falta usarlo)"
          : "AÚN NO AUTENTICADA, escaneá este QR para vincular"
      );
      lastQRTime = now;
    } else {
      console.log("⏱️ QR generado pero omitido (cooldown anti-spam)");
    }
  }

  // 🔄 Estados de conexión
  if (connection === "connecting") {
    console.log("🔄 Conectando...");
  }

  if (connection === "open") {
    console.log("✅ Sesión activa y estable");
    isAuthenticated = true;
    lastQRTime = 0;
    backupAuth();
  }

  if (connection === "close") {
    const code = lastDisconnect?.error?.output?.statusCode;
    console.log(`❌ Conexión cerrada (Código: ${code || "desconocido"})`);

    if (code === DisconnectReason.loggedOut) {
      console.log("⚠️ Sesión cerrada desde el teléfono. No se intentará reconectar.");
      reconnectEnabled = false;
      isAuthenticated = false;
      return;
    }

    if ([408, 440, 500, 515, 428, 401].includes(code)) {
      console.log("♻️ Intentando reconectar en 8s...");
      setTimeout(() => startSock(), 8000);
    } else if (reconnectEnabled) {
      console.log("🔁 Reconectando en 10s...");
      setTimeout(() => startSock(), 10000);
    }
  }
});

app.use((req, _res, next) => {
  console.log(`HTTP ${req.method} ${req.url}`);
  next();
});

app.post('/send', async (req, res) => {
  try {
    console.log('POST /send body:', req.body);

    const { to, phone, message } = req.body || {};

    // Aceptamos tanto "to" como "phone"
    const target = to || phone;

    if (!target || !message) {
      console.log('⚠️ Falta "to/phone" o "message"');
      return res.status(400).json({
        error: 'Debes enviar "to" (o "phone") y "message" en el body JSON',
        received: req.body,
      });
    }

    if (!sock) {
      console.log('⚠️ sock no está inicializado');
      return res.status(503).json({ error: 'WhatsApp no está conectado' });
    }

    const jid = target.includes('@s.whatsapp.net')
      ? target
      : `${target}@s.whatsapp.net`;

    await sock.sendMessage(jid, { text: message });

    console.log(`✅ Mensaje enviado a ${jid}: ${message}`);
    return res.json({ ok: true });
  } catch (err) {
    console.error('Error en /send', err);
    return res.status(500).json({ error: 'Error enviando mensaje' });
  }
});


  sock.ev.on("messages.upsert", async (evt) => {
    try {
      if (evt.type !== "notify") return;
      for (const msg of evt.messages || []) {
        if (msg.key.fromMe) continue;
        const jid = msg.key.remoteJid || "";
        if (jid.includes("-") && jid.endsWith("@g.us")) continue;
        const phone = normalizeE164Plus(jid.split("@")[0] || "");
        const text = extractText(msg);
        if (!phone || !text) continue;
        console.log("[inbound]", { phone, text });

        try {
          const resp = await fetch(N8N_REPLIES_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Secret": N8N_REPLIES_SECRET },
            body: JSON.stringify({ phone, text }),
          });
          console.log(`[agent→n8n] ${resp.status}`);
        } catch (err) {
          console.error("Error enviando a N8N:", err);
        }
      }
    } catch (e) {
      console.error("messages.upsert error:", e);
    }
  });
}

// --- ENDPOINTS PARA CONTROL ---
app.get("/status", (req, res) => {
  res.json({
    connected: !!sock && isAuthenticated,
    authenticated: isAuthenticated,
    timestamp: new Date().toISOString(),
  });
});

app.post("/restart", async (req, res) => {
  console.log("🔁 Reiniciando sesión manualmente...");
  if (sock) try { sock.end(); } catch {}
  isAuthenticated = false;
  reconnectEnabled = true;
  await startSock();
  res.json({ message: "Sesión reiniciada" });
});

// --- STARTUP ---
startSock();
app.listen(3008, "0.0.0.0", () => {
  console.log("📡 Agente WhatsApp VARQ escuchando en puerto 3008");
});
