from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil, uuid
from src.pipeline import parse_document

app = FastAPI(title="doc-parser")

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/parse")
async def parse_api(file: UploadFile = File(...), rules_kie: bool = Form(True)):
    up = Path("uploads")
    up.mkdir(exist_ok=True)
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    fpath = up / fname
    with fpath.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    res = parse_document(str(fpath), use_rules_kie=rules_kie)
    return JSONResponse(content=res)