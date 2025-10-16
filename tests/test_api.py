from fastapi.testclient import TestClient
from app import app
from pathlib import Path

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True

def test_parse_upload(tmp_path):
    # 간단한 PNG 생성
    from PIL import Image
    png = tmp_path / "t.png"
    img = Image.new("RGB", (100, 100), "white")
    img.save(png)
    
    c = TestClient(app)
    with png.open("rb") as f:
        r = c.post("/parse", files={"file": ("t.png", f, "image/png")}, data={"rules_kie": "true"})
    assert r.status_code == 200