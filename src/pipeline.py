from pathlib import Path
from typing import Any
import logging
from .pdf_io import pdf_to_images
from .layout_surya import run_surya_ocr
from .table_ppstruct import SuryaLayoutWrapper
from .form_structure import extract_form_structure, generate_llm_prompt

log = logging.getLogger(__name__)

def parse_document(input_path: str, use_form_analysis: bool = True, **layout_opts) -> dict[str, Any]:
    """
    문서 파싱 메인 함수
    
    Args:
        input_path: 입력 파일 경로 (이미지 또는 PDF)
        use_form_analysis: 양식 구조 분석 활성화
        **layout_opts: Layout wrapper 옵션
    
    Returns:
        파싱 결과 딕셔너리
    """
    log.info(f"문서 파싱 시작: {input_path}")
    
    p = Path(input_path)
    images = [p] if p.suffix.lower() != ".pdf" else pdf_to_images(str(p))
    log.info(f"이미지 {len(images)}개 생성")

    # Surya OCR 실행
    log.info("Surya OCR 실행 중...")
    surya_pages = run_surya_ocr(images)
    log.info(f"OCR 완료: {len(surya_pages)}페이지")

    # Layout + Table 분석
    log.info("Layout 분석 중...")
    layout_wrapper = SuryaLayoutWrapper(**layout_opts)
    layout_out = []
    for im in images:
        layout_out.extend(layout_wrapper.predict(str(im)))
    log.info(f"Layout 분석 완료: {len(layout_out)}개 결과")

    # OCR 라인 추출
    ocr_lines = []
    for page in surya_pages:
        for b in page.get("blocks", []):
            if b.get("text"):
                ocr_lines.append({"text": b["text"], "bbox": b.get("bbox")})
    log.info(f"OCR 라인 추출: {len(ocr_lines)}개")

    # 양식 구조 분석
    form_structure = None
    llm_prompt = None
    if use_form_analysis:
        log.info("양식 구조 분석 중...")
        form_structure = extract_form_structure(ocr_lines, layout_out)
        llm_prompt = generate_llm_prompt(form_structure)
        log.info("LLM 프롬프트 생성 완료")
    
    result = {
        "pages": len(images),
        "form_structure": form_structure,
        "llm_prompt": llm_prompt,
        "layout": layout_out,
        "ocr_lines": ocr_lines
    }
    
    log.info(f"문서 파싱 완료: {len(images)}페이지")
    return result