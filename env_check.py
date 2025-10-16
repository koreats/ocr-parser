import argparse
import logging
import platform
import sys
from pathlib import Path

log = logging.getLogger("env_check")

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

def log_sysinfo():
    log.info("Python: %s", sys.version.split()[0])
    log.info("Platform: %s", platform.platform())
    log.info("Machine: %s", platform.machine())
    log.info("Executable: %s", sys.executable)

def try_import(name, attr="__version__"):
    try:
        mod = __import__(name)
        ver = getattr(mod, attr, "unknown")
        log.info("OK import %-20s version=%s", name, ver)
        return mod
    except Exception as e:
        log.error("FAIL import %s: %s", name, e)
        return None

def check_torch():
    try:
        torch = try_import("torch")
        if torch:
            cuda = torch.cuda.is_available()
            mps = getattr(torch.backends, "mps", None)
            mps_ok = mps.is_available() if mps else False
            log.info("torch cuda=%s mps=%s", cuda, mps_ok)
    except Exception as e:
        log.warning("torch check failed: %s", e)

def check_paddle():
    """PaddlePaddle은 Apple Silicon에서 호환성 문제가 있을 수 있음"""
    try:
        paddle = try_import("paddle")
        if paddle:
            has_cuda = paddle.is_compiled_with_cuda()
            log.info("paddle compiled_with_cuda=%s", has_cuda)
    except Exception as e:
        log.warning("paddle check skipped (Apple Silicon 호환성 이슈 가능): %s", e)

def render_pdf_pymupdf(pdf_path: Path, out_path: Path, dpi=144):
    import fitz
    doc = fitz.open(pdf_path.as_posix())
    page = doc.load_page(0)
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(out_path.as_posix())
    doc.close()
    log.info("PyMuPDF render: %s -> %s", pdf_path.name, out_path.name)

def render_pdf_pdfium(pdf_path: Path, out_path: Path, scale=2.0):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path.as_posix())
    page = pdf.get_page(0)
    bitmap = page.render(scale=scale).to_pil()
    bitmap.save(out_path.as_posix())
    page.close()
    pdf.close()
    log.info("pypdfium2 render: %s -> %s", pdf_path.name, out_path.name)

def smoke_surya(img_path: Path):
    """Surya-OCR 0.17.0+ API 사용"""
    try:
        from PIL import Image
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        
        log.info("Loading Surya models (첫 실행 시 모델 다운로드 발생)...")
        image = Image.open(img_path)
        
        foundation_predictor = FoundationPredictor()
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor()
        
        predictions = recognition_predictor([image], det_predictor=detection_predictor)
        
        if predictions and len(predictions) > 0:
            text_lines = predictions[0].text_lines
            sample_text = " ".join([line.text for line in text_lines[:3]])
            log.info("surya text sample: %s", sample_text[:80])
            log.info("surya detected %d text lines", len(text_lines))
        else:
            log.info("surya produced no text")
    except Exception as e:
        log.warning("surya smoke skipped: %s", e)

def smoke_paddleocr(img_path: Path):
    """PaddleOCR은 Apple Silicon에서 작동하지 않을 수 있음"""
    try:
        from paddleocr import PaddleOCR
        log.info("Attempting PaddleOCR (may fail on Apple Silicon)...")
        ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
        result = ocr.ocr(img_path.as_posix(), cls=True)
        if result and result[0]:
            sample = " ".join([line[1][0] for line in result[0][:5]])
            log.info("paddleocr text sample: %s", sample[:80])
        else:
            log.info("paddleocr produced no lines")
    except Exception as e:
        log.warning("paddleocr smoke skipped (expected on Apple Silicon): %s", e)

def main():
    setup_logging()
    log_sysinfo()

    # 핵심 라이브러리 체크
    log.info("=== Core Libraries ===")
    try_import("fitz", "__version__")  # pymupdf
    try_import("pypdfium2")
    try_import("fastapi")
    try_import("uvicorn")
    try_import("onnxruntime")
    try_import("pydantic")
    try_import("numpy")
    try_import("PIL", "__version__")
    try_import("cv2", "__version__")
    try_import("rapidfuzz")
    try_import("shapely")
    try_import("surya")

    log.info("=== ML Frameworks ===")
    check_torch()
    check_paddle()

    # 명령행 인자 처리
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=str, help="테스트용 PDF 경로")
    ap.add_argument("--img", type=str, help="테스트용 이미지 경로")
    args = ap.parse_args()

    if args.pdf:
        pdf = Path(args.pdf)
        if not pdf.exists():
            log.error("PDF not found: %s", pdf)
            sys.exit(2)
        out1 = pdf.with_suffix(".pymupdf.png")
        out2 = pdf.with_suffix(".pdfium.png")
        try:
            render_pdf_pymupdf(pdf, out1)
        except Exception as e:
            log.error("PyMuPDF raster failed: %s", e)
        try:
            render_pdf_pdfium(pdf, out2)
        except Exception as e:
            log.error("pypdfium2 raster failed: %s", e)

    if args.img:
        img = Path(args.img)
        if not img.exists():
            log.error("Image not found: %s", img)
            sys.exit(3)
        log.info("=== OCR Smoke Tests ===")
        smoke_surya(img)
        smoke_paddleocr(img)

    log.info("=== Environment Check Complete ===")

if __name__ == "__main__":
    main()