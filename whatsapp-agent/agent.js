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
let reconnectAttempts = 0;

// --- STOP FILE ---
const STOP_FILE = "./stopped.json";

function ensureStopFile() {
  try {
    if (!fs.existsSync(STOP_FILE)) fs.writeFileSync(STOP_FILE, JSON.stringify({}, null, 2));
  } catch (e) {
    logger.warn("⚠️ No pude crear stopped.json:", e.message);
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
    logger.warn("⚠️ No pude guardar stopped.json:", e.message);
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
    logger.warn("⚠️ Backup falló:", e.message);
  }
}
function restoreAuth() {
  if (!hasAuth() && fs.existsSync(path.join(AUTH_BACKUP_DIR, "creds.json"))) {
    logger.info("♻️ Restaurando sesión desde backup...");
    fs.cpSync(AUTH_BACKUP_DIR, AUTH_DIR, { recursive: true });
  }
}
function clearAuth() {
  logger.warn("🗑️ Limpiando credenciales...");
  try {
    const files1 = fs.readdirSync(AUTH_DIR);
    for (const f of files1) fs.unlinkSync(path.join(AUTH_DIR, f));
  } catch (e) {}
  try {
    const files2 = fs.readdirSync(AUTH_BACKUP_DIR);
    for (const f of files2) fs.unlinkSync(path.join(AUTH_BACKUP_DIR, f));
  } catch (e) {}
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
  // ⚠️ Cerrar socket anterior si existe para evitar zombies
  if (sock) {
    logger.info("🔄 Cerrando socket anterior antes de reconectar...");
    try {
      sock.ev.removeAllListeners();
      sock.ws.close();
    } catch (e) {
      // ignorar errores al cerrar socket viejo
    }
    sock = null;
  }

  isReconnecting = false;
  ensureDirs();
  ensureStopFile();
  restoreAuth();

  logger.info(`🚀 Iniciando socket... (auth existente: ${hasAuth()})`);

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

    // 🟢 Mostrar QR SIEMPRE que Baileys lo genere (sin cooldown)
    if (qr) {
      console.log("\n================================================");
      console.log("🟢 Escaneá este QR con WhatsApp (Estudio VARQ):");
      qrcode.generate(qr, { small: true });
      console.log("================================================");
    }

    if (connection === "open") {
      logger.info("✅ Sesión de WhatsApp activa");
      isConnected = true;
      isReconnecting = false;
      reconnectAttempts = 0;
      backupAuth();
    }

    if (connection === "close") {
      isConnected = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      const reason = lastDisconnect?.error?.message;
      
      logger.warn({ code, reason }, "⚠️ Conexión de WhatsApp cerrada");

      // Códigos que requieren borrar credenciales y escanear QR nuevo
      const needsNewAuth = (
        code === DisconnectReason.loggedOut ||
        code === 405 ||
        code === 401
      );

      if (needsNewAuth) {
        // Si auth ya está vacía, no re-borrar, solo reintentar con backoff más largo
        if (!hasAuth()) {
          reconnectAttempts++;
          const delay = Math.min(30000 * Math.pow(2, reconnectAttempts - 1), 300000);
          logger.warn(`⏳ Auth ya vacía pero sigue el error ${code}. WhatsApp puede estar limitando. Reintentando en ${delay / 1000}s (intento #${reconnectAttempts})...`);
          isReconnecting = false;
          if (reconnectEnabled) {
            setTimeout(() => startSock(), delay);
          }
        } else {
          logger.error(`🛑 Sesión inválida (código ${code}). Borrando credenciales para escanear nuevo QR...`);
          clearAuth();
          reconnectAttempts = 0;
          isReconnecting = false;
          if (reconnectEnabled) {
            logger.info("⏳ Reiniciando en 5s para mostrar QR nuevo...");
            setTimeout(() => startSock(), 5000);
          }
        }
      } else if (reconnectEnabled && !isReconnecting) {
        isReconnecting = true;
        reconnectAttempts++;
        const delay = Math.min(5000 * Math.pow(2, reconnectAttempts - 1), 60000);
        logger.info(`⏳ Intentando reconectar en ${delay / 1000}s (intento #${reconnectAttempts})...`);
        setTimeout(() => {
          startSock();
        }, delay);
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
      logger.error("messages.upsert error:", e?.message || e);
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
