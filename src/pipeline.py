from pathlib import Path
from typing import Any
import logging
from .pdf_io import pdf_to_images
from .layout_surya import run_surya_ocr
from .table_ppstruct import SuryaLayoutWrapper
from .form_structure import extract_form_structure, generate_llm_prompt, generate_hybrid_prompt

log = logging.getLogger(__name__)

def parse_document(input_path: str, form_analysis: bool = True, **pp_opts) -> dict[str, Any]:
    """
    문서 파싱 파이프라인
    """
    log.info(f"문서 파싱 시작: {input_path}")
    p = Path(input_path)
    images = [p] if p.suffix.lower() != ".pdf" else pdf_to_images(str(p))
    log.info(f"이미지 {len(images)}개 생성")

    surya_pages = run_surya_ocr(images)
    log.info(f"OCR 완료: {len(surya_pages)}페이지")

    pp = SuryaLayoutWrapper(**pp_opts)
    pp_out = []
    for im in images:
        pp_out.extend(pp.predict(str(im)))
    log.info(f"Layout 분석 완료: {len(pp_out)}개 결과")

    ocr_lines = []
    for page in surya_pages:
        for b in page.get("blocks", []):
            if b.get("text"):
                ocr_lines.append({"text": b["text"], "bbox": b.get("bbox")})
    log.info(f"OCR 라인 추출: {len(ocr_lines)}개")

    # 양식 분석
    form_struct = {}
    markdown_prompt = ""
    hybrid_prompt = ""
    
    if form_analysis:
        log.info("양식 구조 분석 중...")
        form_struct = extract_form_structure(ocr_lines, pp_out)
        markdown_prompt = generate_llm_prompt(form_struct)
        hybrid_prompt = generate_hybrid_prompt(ocr_lines, form_struct)
        log.info("LLM 프롬프트 생성 완료")
    
    return_val = {
        "pages": len(images),
        "ppstructure": pp_out,
        "ocr_lines": ocr_lines,
        "form_structure": form_struct,
        "llm_prompt": markdown_prompt,
        "hybrid_prompt": hybrid_prompt
    }
    log.info(f"문서 파싱 완료: {len(images)}페이지")
    return return_val