"""
통합 파이프라인: PDF/이미지 → OCR → 양식 구조 추출
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import logging

from .pdf_io import pdf_to_images
from .layout_surya import run_surya_ocr
from .table_ppstruct import PPStructWrapper
from .form_structure import extract_form_structure

log = logging.getLogger("pipeline")


def parse_document(
    input_path: str, 
    form_analysis: bool = True,
    **pp_opts
) -> dict[str, Any]:
    """
    문서 파싱 파이프라인
    
    Args:
        input_path: 입력 파일 경로 (PDF 또는 이미지)
        form_analysis: 양식 구조 분석 활성화 여부
        **pp_opts: PP-Structure 추가 옵션
    
    Returns:
        파싱 결과 딕셔너리
    """
    log.info(f"파싱 시작: {input_path}")
    
    # 1. PDF → 이미지 변환 (필요시)
    p = Path(input_path)
    if p.suffix.lower() == ".pdf":
        log.info("PDF → 이미지 변환 중...")
        images = pdf_to_images(str(p))
    else:
        images = [p]
    
    log.info(f"총 {len(images)}개 페이지 처리")
    
    # 2. Surya OCR 실행
    log.info("Surya OCR 실행 중...")
    surya_pages = run_surya_ocr(images)
    
    # 3. PP-Structure 표 인식
    log.info("PP-Structure 표 인식 중...")
    pp = PPStructWrapper(**pp_opts)
    pp_out = []
    for im in images:
        pp_out.extend(pp.predict(str(im)))
    
    # 4. OCR 라인 추출
    ocr_lines = []
    for page in surya_pages:
        for b in page.get("blocks", []):
            if b.get("text"):
                ocr_lines.append({
                    "text": b["text"], 
                    "bbox": b.get("bbox")
                })
    
    log.info(f"OCR 라인 추출: {len(ocr_lines)}개")
    
    # 5. 양식 구조 분석 (선택적)
    form_data = {}
    llm_prompt = ""
    
    if form_analysis and ocr_lines:
        log.info("양식 구조 분석 중...")
        
        # 이미지 크기 추정 (첫 번째 이미지 기준)
        # 실제로는 PIL로 읽어서 정확한 크기를 가져오는 게 좋지만,
        # 일단 기본값 사용
        from PIL import Image
        try:
            with Image.open(images[0]) as img:
                image_width, image_height = img.size
        except Exception:
            # 실패 시 기본값
            image_width, image_height = 1200, 3000
        
        form_result = extract_form_structure(
            ocr_lines, 
            image_width=image_width, 
            image_height=image_height
        )
        
        form_data = {
            "total_elements": form_result.get("total_elements", 0),
            "elements_by_type": form_result.get("elements_by_type", {}),
            "spatial_distribution": form_result.get("spatial_distribution", {}),
            "elements": form_result.get("elements", [])
        }
        
        llm_prompt = form_result.get("llm_prompt", "")
        
        log.info(f"양식 요소 추출: {form_data['total_elements']}개")
        log.info(f"LLM 프롬프트 생성: {len(llm_prompt)} 문자")
    
    # 6. 결과 통합
    result = {
        "pages": len(images),
        "ocr_lines": ocr_lines,
        "ppstructure": pp_out
    }
    
    if form_analysis:
        result["form_structure"] = form_data
        result["llm_prompt"] = llm_prompt
    
    log.info("파싱 완료")
    
    return result
