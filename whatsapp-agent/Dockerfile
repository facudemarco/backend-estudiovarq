FROM node:18-slim

# Instalar git (requerido por dependencias npm)
RUN apt-get update && apt-get install -y git

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3008

CMD ["node", "agent.js"]