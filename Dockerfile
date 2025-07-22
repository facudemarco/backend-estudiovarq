FROM python:3.10-slim

# --- Instalaciones base necesarias ---
RUN apt-get update && apt-get install -y \
    curl gnupg build-essential pkg-config default-libmysqlclient-dev git\
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# --- Directorio de trabajo ---
WORKDIR /app

# --- Copiamos e instalamos dependencias de Python ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copiamos el resto del backend ---
COPY . .

# --- Instalamos las dependencias del whatsapp-agent ---
WORKDIR /app/whatsapp-agent
RUN npm install

# --- Volvemos al root del backend ---
WORKDIR /app

# --- Comando de arranque ---
CMD ["sh", "-c", "node whatsapp-agent/agent.js & uvicorn main:app --host 0.0.0.0 --port 8000"]