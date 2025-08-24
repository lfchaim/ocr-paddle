# OCR API – PaddleOCR + Pré-processamento (FastAPI + Docker + Nginx + Rate Limit)

API RESTful para extrair texto de imagens utilizando **PaddleOCR**, com pipeline de pré-processamento configurável,
**limite de upload**, **rate limiting** e opção de **GPU** via perfil no Docker Compose.

## 🚀 Opções de Execução

### 1) Docker (CPU)
```bash
docker build -t ocr-api:cpu -f Dockerfile .
docker run --rm -p 8000:8000 -e MAX_UPLOAD_MB=15 -e RATE_LIMIT=120/minute ocr-api:cpu
```
Swagger: `http://localhost:8000/docs`

### 2) Docker Compose (com Nginx)
```bash
docker compose up -d --build
```
- Nginx expõe `http://localhost/` (proxy para `api` na porta 8000).
- Swagger em `http://localhost/docs`.

### 3) Docker Compose (GPU) – opcional
Requer host com NVIDIA + driver + runtime.
```bash
docker compose --profile gpu up -d --build
```
- API GPU em `http://localhost:8001`.

> Obs.: O `Dockerfile.gpu` remove `paddlepaddle` (CPU) e instala `paddlepaddle-gpu`. Ajuste a versão conforme sua CUDA.

## 🔧 Endpoints
- `GET /health` – Health check
- `POST /ocr` – Recebe `multipart/form-data` com campo `file` (imagem) e query params:
  - `lang`: `en` ou `pt` (para pt usamos o modelo `latin` do PaddleOCR)
  - `contrast`: 0-100 (padrão 50)
  - `sharpness`: 0-100 (padrão 50)
  - `binarization`: `simple` ou `adaptive` (padrão `adaptive`)
  - `resize_width`: largura alvo para redimensionamento (padrão 1600)

### Exemplo (cURL)
```bash
curl -X POST "http://localhost/ocr?lang=pt&contrast=50&sharpness=75&binarization=adaptive" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/caminho/para/sua/imagem.jpg"
```

### Resposta
```json
{"texto": "Texto extraído da imagem após processamento"}
```

## ⚙️ Configuração por Ambiente
- `LOG_LEVEL` (default: `INFO`)
- `MAX_UPLOAD_MB` (default: `10`) – tamanho máximo do arquivo aceito pela API
- `RATE_LIMIT` (default: `60/minute`) – ex.: `120/minute`, `1000/hour`

## 🧪 Testes
```bash
pip install -r requirements.txt
pytest -q
```

## 📓 Notas Técnicas
- **Idioma PT**: mapeado para o modelo `latin` do PaddleOCR (alfabetos latinos, cobre PT).
- **Deskew**: correção de orientação baseada em morfologia/minAreaRect (ângulos moderados).
- **Denoise**: `bilateralFilter` + `fastNlMeansDenoisingColored`.
- **Binarização**: Otsu (`simple`) ou `adaptiveThreshold` (gaussiano).
- **Desempenho**: Instâncias do OCR são **cacheadas** por idioma (LRU cache).
- **Rate Limiting**: `slowapi` (por IP). 429 quando exceder limite.
- **Nginx**: `client_max_body_size` configurável; proxy para API.

## 🛡️ Segurança e Robustez
- Validação de tamanho e Content-Type.
- Tratamento de exceções com mensagens claras (400/415/413/429/500).
- CORS liberado (ajuste `allow_origins` em produção).

## 🧭 Roadmap
- Persistência de imagens processadas.
- Métricas Prometheus.
- Fila assíncrona para cargas pesadas.

## Build

```bash
$ sudo docker build -t ocr-paddle:latest .
```

## Run

```bash
$ sudo docker run --rm -p 8000:8000 ocr-paddle:latest
```

## API Test
```bash
curl --location 'http://localhost:8000/ocr?lang=en&contrast=30&sharpness=75&binarization=adaptive' \
--header 'accept: application/json' \
--form 'file=@"/home/fernando/Downloads/IMG_20250821_161044.jpg"'
```
