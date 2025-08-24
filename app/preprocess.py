import logging
from typing import Literal, Tuple, Optional

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger("ocr_preprocess")

# Utilidades ----------------------------
def _pil_to_cv2(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def _cv2_to_pil(mat: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(mat, cv2.COLOR_BGR2RGB))

# Passos de pré-processamento -----------
def adjust_contrast_and_sharpness(img: Image.Image, contrast: int, sharpness: int) -> Image.Image:
    """Ajusta contraste e nitidez usando PIL (0-100). 50 = neutro."""
    # Normaliza para fatores das classes ImageEnhance
    def scale(v: int, neutral: float = 1.0, span: float = 1.5):
        # v=50 -> 1.0, v=0 -> ~0.0, v=100 -> ~2.0 (span controla alcance)
        return max(0.0, neutral + (v - 50) / 50.0 * span)

    c_factor = scale(contrast, span=1.5)
    s_factor = scale(sharpness, span=1.8)

    img = ImageEnhance.Contrast(img).enhance(c_factor)
    img = ImageEnhance.Sharpness(img).enhance(s_factor)
    return img

def resize_image_cv2(bgr: np.ndarray, target_width: Optional[int]) -> np.ndarray:
    if not target_width or target_width <= 0:
        return bgr
    h, w = bgr.shape[:2]
    if w == target_width:
        return bgr
    scale = target_width / float(w)
    new_h = max(1, int(h * scale))
    return cv2.resize(bgr, (target_width, new_h), interpolation=cv2.INTER_CUBIC)

def denoise(bgr: np.ndarray) -> np.ndarray:
    # Combina blur bilateral (preserva bordas) e NlMeans
    den = cv2.bilateralFilter(bgr, d=9, sigmaColor=75, sigmaSpace=75)
    den = cv2.fastNlMeansDenoisingColored(den, None, 3, 3, 7, 21)
    return den

def deskew(bgr: np.ndarray) -> np.ndarray:
    """Corrige rotação leve baseada em morfologia e minAreaRect.
    Funciona bem para texto com orientação até ~15°."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # binariza levemente para destacar componentes
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    # inverte se necessário para ter texto em preto
    if np.mean(thr) > 127:
        thr = 255 - thr

    # fecha gaps horizontais (texto)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
    morph = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=1)

    # encontra contornos e maior área
    cnts, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return bgr
    c = max(cnts, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    angle = float(np.clip(angle, -15, 15))

    if abs(angle) < 0.5:
        return bgr

    h, w = bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(bgr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def binarize(bgr: np.ndarray, mode: Literal["simple", "adaptive"]) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if mode == "simple":
        _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 35, 11)
    # retorna em 3 canais para manter compatibilidade
    return cv2.cvtColor(thr, cv2.COLOR_GRAY2BGR)

def preprocess_image(
    pil_img: Image.Image,
    *,
    contrast: int,
    sharpness: int,
    binarization: Literal["simple", "adaptive"],
    resize_width: Optional[int] = 1600,
):
    """Pipeline completo de pré-processamento.

    Retorna (imagem_bgr_cv2, imagem_pil) pós-processadas.
    """
    # 1) Contraste & Nitidez com PIL
    img = adjust_contrast_and_sharpness(pil_img, contrast, sharpness)

    # 2) Converte para OpenCV e redimensiona
    bgr = _pil_to_cv2(img)
    bgr = resize_image_cv2(bgr, resize_width)

    # 3) Remoção de ruído
    bgr = denoise(bgr)

    # 4) Correção de orientação (deskew)
    bgr = deskew(bgr)

    # 5) Binarização
    bgr = binarize(bgr, binarization)

    # Retorna também em PIL para debug/uso externo, se necessário
    return bgr, _cv2_to_pil(bgr)