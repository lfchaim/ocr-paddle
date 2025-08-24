FROM python:3.10-slim

# Dependências do sistema para OpenCV e Paddle
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

EXPOSE 8000

# Variáveis de ambiente
ENV LOG_LEVEL=INFO \
    MAX_UPLOAD_MB=10 \
    RATE_LIMIT=60/minute

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]