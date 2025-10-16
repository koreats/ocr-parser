from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import uuid
from src.pipeline import parse_document

app = FastAPI(title="doc-parser")

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/parse")
async def parse_api(file: UploadFile = File(...), rules_kie: bool = Form(False)):
    up = Path("uploads")
    up.mkdir(exist_ok=True)
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    fpath = up / fname
    
    with fpath.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # form_analysis=True로 항상 양식 분석 수행
    res = parse_document(str(fpath), use_rules_kie=rules_kie, use_form_analysis=True)
    
    return JSONResponse(content=res)