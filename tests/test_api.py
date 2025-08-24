import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_ocr_unsupported_file():
    # Envia payload vazio
    r = client.post("/ocr", files={"file": ("empty.jpg", b"", "image/jpeg")})
    assert r.status_code == 400

def test_ocr_happy_path_sample_text():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (600, 200), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 80), "Hello World", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    r = client.post(
        "/ocr",
        params={"lang": "en", "contrast": 60, "sharpness": 60, "binarization": "adaptive"},
        files={"file": ("test.png", buf.read(), "image/png")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "texto" in data
    assert isinstance(data["texto"], str)