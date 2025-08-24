import io
import logging
import os
from functools import lru_cache
from typing import Literal, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image

# Rate limiting (SlowAPI)
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Swagger metadata
app = FastAPI(
    title="OCR API – PaddleOCR + Preprocess",
    description=(
        "API RESTful para extração de texto com PaddleOCR, com pré-processamento avançado.\n"
        "Parâmetros de query permitem controlar contraste, nitidez, binarização e idioma."
    ),
    version="1.1.0",
)

# CORS (ajuste conforme necessidade)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging básico
logger = logging.getLogger("ocr_api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Rate Limiter
rate_limit = os.getenv("RATE_LIMIT", "60/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}))
app.add_middleware(SlowAPIMiddleware)

# Importa funções de preprocessamento
from .preprocess import preprocess_image

try:
    from paddleocr import PaddleOCR
except Exception as e:
    logger.error("Falha ao importar PaddleOCR: %s", e)
    raise

# Cache de instâncias do OCR por idioma para evitar recarregamentos custosos
_SUPPORTED_LANGS = {"en": "en", "pt": "latin"}  # mapeia pt -> modelo 'latin' (cobre PT/ES/FR etc.)

@lru_cache(maxsize=4)
def get_ocr(lang: Literal["en", "pt"]) -> "PaddleOCR":
    mapped = _SUPPORTED_LANGS[lang]
    logger.info("Inicializando PaddleOCR para lang=%s (modelo=%s)", lang, mapped)
    # use_angle_cls melhora correção de orientação de texto, show_log False reduz verbosidade
    ocr = PaddleOCR(use_angle_cls=True, lang=mapped, show_log=False)
    return ocr

class OCRResponse(JSONResponse):
    pass

@app.get("/health", tags=["infra"])
@limiter.limit("120/minute")
def health_check(request:Request):
    return {"status": "ok"}

def _enforce_upload_limits(request: Request, content: bytes):
    # Limite de tamanho (em MB)
    max_mb = float(os.getenv("MAX_UPLOAD_MB", "10"))
    max_bytes = int(max_mb * 1024 * 1024)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo excede {max_mb} MB.")
    # Mimetype básico
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" not in ctype:
        # Permite somente multipart para evitar uploads incorretos
        raise HTTPException(status_code=415, detail="Content-Type inválido. Use multipart/form-data.")
    return True

@app.post("/ocr", tags=["ocr"], summary="Extrai texto de uma imagem")
@limiter.limit(os.getenv("RATE_LIMIT", "60/minute"))
async def ocr_endpoint(
    request: Request,
    file: UploadFile = File(..., description="Arquivo de imagem (jpg, png, etc.)"),
    lang: Literal["en", "pt"] = Query("pt", description="Idioma do texto na imagem"),
    contrast: int = Query(50, ge=0, le=100, description="Nível de contraste (0-100)"),
    sharpness: int = Query(50, ge=0, le=100, description="Nível de nitidez (0-100)"),
    binarization: Literal["simple", "adaptive"] = Query(
        "adaptive", description="Tipo de binarização"
    ),
    resize_width: Optional[int] = Query(
        1600, ge=0, description="Largura alvo para redimensionamento (0 para manter)"
    ),
):
    """Recebe uma imagem, aplica pré-processamento e extrai texto via PaddleOCR."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Imagem vazia ou inválida.")

        _enforce_upload_limits(request, content)

        # Carrega imagem em PIL
        try:
            pil_img = Image.open(io.BytesIO(content)).convert("RGB")
        except Exception:
            raise HTTPException(status_code=415, detail="Formato de imagem não suportado.")

        # Pré-processa (PIL in -> OpenCV out e PIL out compatível)
        proc_bgr, _ = preprocess_image(
            pil_img,
            contrast=contrast,
            sharpness=sharpness,
            binarization=binarization,
            resize_width=resize_width,
        )

        # OCR
        ocr = get_ocr(lang)
        # PaddleOCR aceita caminho ou array; usaremos array (BGR -> RGB)
        rgb = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2RGB)
        result = ocr.ocr(rgb, cls=True)

        # Agrega linhas em ordem de detecção
        lines = []
        for page in result:
            for line in page:
                txt = line[1][0]
                if txt:
                    lines.append(txt)
        texto = "\n".join(lines).strip()

        return JSONResponse(status_code=200, content={"texto": texto})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro durante OCR: %s", e)
        raise HTTPException(status_code=500, detail="Falha interna ao processar a imagem.")