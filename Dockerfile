FROM python:3.10-slim

# --- Instalaciones base necesarias ---
RUN apt-get update && apt-get install -y \
    curl gnupg build-essential pkg-config default-libmysqlclient-dev git\
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]