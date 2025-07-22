const makeWASocket = require('baileys').default;
const { useSingleFileAuthState } = require('baileys');
const { Boom } = require('@hapi/boom');
const fs = require('fs');

const { state, saveState } = useSingleFileAuthState('./auth.json');

const phone = process.argv[2];
const message = process.argv[3];

async function start() {
  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
  });

  sock.ev.on('connection.update', (update) => {
    if (update.connection === 'open') {
      sock.sendMessage(`${phone}@s.whatsapp.net`, { text: message });
    }
  });

  sock.ev.on('creds.update', saveState);
}

start();