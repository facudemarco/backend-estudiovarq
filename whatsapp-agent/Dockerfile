FROM node:20-slim

WORKDIR /app

# 🔧 deps del sistema: git (para npm), y build tools por si algún paquete los necesita
RUN apt-get update && \
    apt-get install -y git python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

# 📦 inicializamos proyecto y instalamos dependencias del agente
RUN npm init -y && \
    npm install express @whiskeysockets/baileys pino pino-pretty qrcode-terminal

# 📁 copiamos el agente
COPY agent.js ./

# carpetas para sesiones
RUN mkdir -p /app/auth /app/auth_backup

EXPOSE 3008

CMD ["node", "agent.js"]