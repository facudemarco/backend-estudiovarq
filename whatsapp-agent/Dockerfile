FROM node:20-alpine

WORKDIR /app

# 🔧 deps del sistema: git (para npm), y build tools por si algún paquete los necesita
RUN apk add --no-cache git python3 make g++

# 📦 inicializamos proyecto y instalamos dependencias del agente
RUN npm init -y && \
    npm install express @whiskeysockets/baileys pino pino-pretty qrcode-terminal qrcode cors

# 📁 copiamos el agente
COPY agent.js ./

# carpetas para sesiones
RUN mkdir -p /app/auth /app/auth_backup /data/wa_backups

EXPOSE 3008

# 🛡️ Graceful shutdown: Docker enviará SIGTERM al parar
STOPSIGNAL SIGTERM

CMD ["node", "agent.js"]
