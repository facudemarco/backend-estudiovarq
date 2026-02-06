global.crypto = require("node:crypto");
const express = require("express");
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const pino = require("pino");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// Node 18+ trae fetch. Si estás en 16, instalá node-fetch e importalo.
// const fetch = require("node-fetch");

const app = express();
app.use(express.json());

const logger = pino({ level: "info" });

// --- CONFIG ---
const AUTH_DIR = "./auth";
const AUTH_BACKUP_DIR = "./auth_backup";

const N8N_REPLIES_URL =
  process.env.N8N_REPLIES_URL || "https://n8n.iwebtecnology.com/webhook/estudiovarq-replies";
const N8N_REPLIES_SECRET =
  process.env.N8N_REPLIES_SECRET || "MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_EstudioVARq";

let sock;
let reconnectEnabled = true;
let isAuthenticated = false;
let lastQRTime = 0;
const QR_COOLDOWN_MS = 60000;

// --- STOP FILE ---
const STOP_FILE = "./stopped.json";

function ensureStopFile() {
  try {
    if (!fs.existsSync(STOP_FILE)) {
      fs.writeFileSync(STOP_FILE, JSON.stringify({}, null, 2));
    }
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

  // Si no hay texto pero hay media
  if (m.imageMessage || m.videoMessage || m.audioMessage || m.documentMessage || m.stickerMessage) {
    return "[media]";
  }
  return "";
}

// --- MAIN FUNCTION ---
async function startSock() {
  ensureDirs();
  ensureStopFile();
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
      console.log("✅ Sesión activa");
      isAuthenticated = true;
      backupAuth();
    }

    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      isAuthenticated = false;
      if (code !== DisconnectReason.loggedOut && reconnectEnabled) {
        setTimeout(() => startSock(), 10000);
      }
    }
  });

  // --- INBOUND LOGIC ---
  sock.ev.on("messages.upsert", async (evt) => {
    try {
      if (evt.type !== "notify") return;

      for (const msg of evt.messages || []) {
        if (!msg?.key) continue;
        if (msg.key.remoteJid === "status@broadcast") continue;

        const jid = msg.key.remoteJid || "";
        if (jid.includes("-") && jid.endsWith("@g.us")) continue; // grupos afuera

        const phone = normalizeE164Plus(jid.split("@")[0] || "");
        if (!phone) continue;

        const text = extractText(msg);
        const rawMessageKeys = Object.keys(msg.message || {});

        // Debug inbound real
        console.log("[debug-inbound]", {
          phone,
          fromMe: !!msg.key.fromMe,
          rawMessage: rawMessageKeys,
          text,
        });

        // ✅ STOP: cualquier mensaje entrante humano corta seguimiento
        if (!msg.key.fromMe) {
          const stopped = loadStopped();
          if (!stopped[phone]) {
            stopped[phone] = true;
            saveStopped(stopped);
            console.log(`[flow-stopped] Cliente ${phone} respondió. Seguimiento cortado.`);
          }
        }

        // Enviar a n8n (aunque sea media / vacío)
        await fetch(N8N_REPLIES_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Secret": N8N_REPLIES_SECRET,
          },
          body: JSON.stringify({ phone, text, rawMessage: rawMessageKeys }),
        }).catch((e) => console.error("Error enviando a N8N:", e?.message || e));
      }
    } catch (e) {
      console.error("messages.upsert error:", e?.message || e);
    }
  });
}

// --- ENDPOINTS ---
app.post("/send", async (req, res) => {
  try {
    const { to, phone, message } = req.body || {};
    const targetRaw = to || phone;
    const target = normalizeE164Plus(targetRaw);

    if (!target || !message || !sock) {
      return res.status(400).json({ error: "Datos insuficientes o socket no listo" });
    }

    const stopped = loadStopped();
    if (stopped[target]) {
      console.log(`[blocked-send] ${target} está marcado como intervenido`);
      return res.json({ ok: false, stopped: true });
    }

    const jid = `${target.replace("+", "")}@s.whatsapp.net`;

    // ✅ Link preview off (evita link-preview-js error)
    await sock.sendMessage(jid, { text: String(message) }, { disableLinkPreview: true });

    return res.json({ ok: true });
  } catch (err) {
    return res.status(500).json({ error: err?.message || String(err) });
  }
});

app.post("/unstopp", (req, res) => {
  const raw = req.body?.phone;
  const target = normalizeE164Plus(raw);

  const stopped = loadStopped();
  delete stopped[target];
  saveStopped(stopped);

  res.json({ ok: true, phone: target });
});

// --- STARTUP ---
startSock();
app.listen(3008, "0.0.0.0", () => {
  console.log("📡 Agente WhatsApp VARQ en puerto 3008");
});
