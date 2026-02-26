global.crypto = require("node:crypto");
const express = require("express");
const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} = require("@whiskeysockets/baileys");
const pino = require("pino");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(express.json());

const logger = pino({
  level: "info",
  timestamp: () => `,"time":"${new Date().toISOString()}"`,
  formatters: {
    level(label) { return { level: label }; },
  },
});

// Logger silencioso para Baileys para evitar spam en la terminal
const baileysLogger = pino({ level: "silent" });

// --- CONFIG ---
const AUTH_DIR = "./auth";
const AUTH_BACKUP_DIR = "./auth_backup";

const N8N_REPLIES_URL =
  process.env.N8N_REPLIES_URL ||
  "https://n8n.iwebtecnology.com/webhook/estudiovarq-reply";

const N8N_INBOUND_URL =
  process.env.N8N_INBOUND_URL ||
  "https://n8n.iwebtecnology.com/webhook/estudiovarq-inbound";

const N8N_REPLIES_SECRET =
  process.env.N8N_REPLIES_SECRET ||
  "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq";

let sock;
let reconnectEnabled = true;
let isReconnecting = false;
let isConnected = false;
let lastQRTime = 0;
const QR_COOLDOWN_MS = 60000;

// --- STOP FILE ---
const STOP_FILE = "./stopped.json";

function ensureStopFile() {
  try {
    if (!fs.existsSync(STOP_FILE)) fs.writeFileSync(STOP_FILE, JSON.stringify({}, null, 2));
  } catch (e) {
    console.log("⚠️ No pude crear stopped.json:", e.message);
  }
}

function loadStopped() {
  try {
    ensureStopFile();
    const raw = fs.readFileSync(STOP_FILE, "utf-8");
    const parsed = JSON.parse(raw || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveStopped(data) {
  try {
    fs.writeFileSync(STOP_FILE, JSON.stringify(data || {}, null, 2));
  } catch (e) {
    console.log("⚠️ No pude guardar stopped.json:", e.message);
  }
}

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
    if (hasAuth()) fs.cpSync(AUTH_DIR, AUTH_BACKUP_DIR, { recursive: true });
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
  if (m.documentWithCaptionMessage?.message)
    return extractText({ message: m.documentWithCaptionMessage.message });

  const txt =
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    m.templateButtonReplyMessage?.selectedId ||
    "";

  if (txt && String(txt).trim()) return String(txt).trim();

  // si hay media sin texto
  if (m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage) {
    return "[media]";
  }
  return "";
}

// --- MAIN ---
async function startSock() {
  ensureDirs();
  ensureStopFile();
  restoreAuth();

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  sock = makeWASocket({
    auth: state,
    logger: baileysLogger,
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

    if (qr) {
      const now = Date.now();
      if (now - lastQRTime > QR_COOLDOWN_MS) {
        console.log("\n================================================");
        console.log("🟢 Escaneá este QR con WhatsApp (Estudio VARQ):");
        qrcode.generate(qr, { small: true });
        console.log("================================================");
        lastQRTime = now;
      }
    }

    if (connection === "open") {
      logger.info("✅ Sesión de WhatsApp activa");
      isConnected = true;
      isReconnecting = false;
      backupAuth();
    }

    if (connection === "close") {
      isConnected = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      const reason = lastDisconnect?.error?.message;
      
      logger.warn({ code, reason }, "⚠️ Conexión de WhatsApp cerrada");

      if (code === DisconnectReason.loggedOut) {
        logger.error("🛑 Sesión cerrada (logged out). Borrando credenciales para escanear nuevo QR...");
        try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (e) {}
        try { fs.rmSync(AUTH_BACKUP_DIR, { recursive: true, force: true }); } catch (e) {}
        
        if (reconnectEnabled) {
          isReconnecting = false;
          startSock();
        }
      } else if (reconnectEnabled && !isReconnecting) {
        isReconnecting = true;
        logger.info("⏳ Intentando reconectar en 5 segundos...");
        setTimeout(() => {
          startSock();
        }, 5000);
      }
    }
  });

  sock.ev.on("messages.upsert", async (evt) => {
    try {
      if (evt.type !== "notify") return;

      for (const msg of evt.messages || []) {
        if (!msg?.key) continue;
        if (msg.key.remoteJid === "status@broadcast") continue;

        const jid = msg.key.remoteJid || "";
        if (jid.includes("-") && jid.endsWith("@g.us")) continue; // grupos no

        const phone = normalizeE164Plus(jid.split("@")[0] || "");
        if (!phone) continue;

        const text = extractText(msg);
        const rawMessageKeys = Object.keys(msg.message || {});
        const fromMe = !!msg.key.fromMe;

        logger.info({ phone, fromMe, text }, "📥 Mensaje entrante");

        // ✅ SI ES NUESTRO MENSAJE, NO LO REENVIAMOS A N8N (ANTI-LOOP)
        if (fromMe) continue;

        // ✅ STOP: cualquier mensaje humano (texto o media) corta seguimiento
        const stopped = loadStopped();
        if (!stopped[phone]) {
          stopped[phone] = true;
          saveStopped(stopped);
          logger.info(`🚫 [flow-stopped] Cliente ${phone} respondió. Seguimiento automático cortado.`);
        }

        // Enviar solo mensajes reales del cliente a n8n
        const payload = { phone, text, rawMessage: rawMessageKeys };

        await Promise.allSettled([
          fetch(N8N_REPLIES_URL, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Secret": N8N_REPLIES_SECRET,
            },
            body: JSON.stringify(payload),
          }),
          fetch(N8N_INBOUND_URL, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Secret": N8N_REPLIES_SECRET,
            },
            body: JSON.stringify(payload),
          }),
        ]).catch(() => {});
      }
    } catch (e) {
      console.error("messages.upsert error:", e?.message || e);
    }
  });
}

// --- ENDPOINTS ---
app.post("/send", async (req, res) => {
  try {
    const { to, phone, message, force } = req.body || {};
    const targetRaw = to || phone;
    const target = normalizeE164Plus(targetRaw);

    if (!target || !message) {
      return res.status(400).json({ error: "Datos de envío insuficientes" });
    }

    if (!sock || !isConnected) {
      logger.error("Intento de envío fallido: Socket no listo o desconectado");
      return res.status(503).json({ error: "El agente de WhatsApp no está conectado en este momento. Inténtelo más tarde." });
    }

    const stopped = loadStopped();
    if (stopped[target] && !force) {
      logger.info(`[blocked-send] ${target} está marcado como intervenido de forma manual`);
      return res.json({ ok: false, stopped: true });
    }

    const jid = `${target.replace("+", "")}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text: String(message) }, { disableLinkPreview: true });

    logger.info(`✅ Mensaje enviado a ${target}`);
    return res.json({ ok: true });
  } catch (err) {
    logger.error({ err: err?.message || String(err) }, "❌ Error al enviar mensaje desde endpoint /send");
    return res.status(500).json({ error: "Error interno al enviar el mensaje" });
  }
});

app.post("/unstopp", (req, res) => {
  const target = normalizeE164Plus(req.body?.phone);
  const stopped = loadStopped();

  delete stopped[target];
  saveStopped(stopped);

  res.json({ ok: true, phone: target });
});

app.post("/status", (req, res) => {
  const target = normalizeE164Plus(req.body?.phone);
  if (!target) return res.status(400).json({ ok: false, error: "phone required" });

  const stopped = loadStopped();
  return res.json({ ok: true, phone: target, stopped: !!stopped[target] });
});

// --- STARTUP ---
startSock();
app.listen(3008, "0.0.0.0", () => {
  console.log("📡 Agente WhatsApp VARQ en puerto 3008");
});
