"""
범용 양식 구조 추출 및 LLM 프롬프트 생성
계층적 하이브리드 전략 적용
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any
from collections import defaultdict
from .layered_describer import LayeredFormDescriber

log = logging.getLogger("form_structure")

def extract_form_structure(ocr_lines: list[dict], image_width: int = 1200, image_height: int = 3000) -> dict[str, Any]:
    """
    OCR 결과에서 양식 구조 추출 (개선된 버전)
    """
    # 기존 요소 분류 로직 유지
    elements = []
    step = 1
    
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox")
        
        if not text or not bbox:
            continue
        
        x, y, x2, y2 = bbox
        width = x2 - x
        height = y2 - y
        area = width * height
        
        elem_type = _classify_element_type(text, width, height, area)
        
        elements.append({
            "step": step,
            "label": text,
            "type": elem_type,
            "position": {"x": x, "y": y},
            "width": width,
            "height": height,
            "bbox": bbox
        })
        step += 1
    
    # 계층적 하이브리드 전략 적용
    describer = LayeredFormDescriber(doc_width=image_width, doc_height=image_height)
    llm_prompt = describer.describe_for_llm(elements, ocr_lines)
    
    # 통계 정보
    stats = _calculate_statistics(elements)
    
    return {
        "total_elements": len(elements),
        "elements_by_type": stats["by_type"],
        "spatial_distribution": stats["spatial"],
        "elements": elements,
        "llm_prompt": llm_prompt
    }


def _classify_element_type(text: str, width: int, height: int, area: int) -> str:
    """요소 타입 분류"""
    text_lower = text.lower()
    
    # 버튼 감지
    button_keywords = ['등록', '저장', '삭제', '추가', '확인', '취소', '다음', '이전', '검색', '제출', '완료']
    if any(kw in text for kw in button_keywords) and area < 5000:
        return "buttons"
    
    # 체크박스/라디오
    if text in ['□', '☐', '○', '◯'] or (len(text) <= 2 and area < 500):
        return "checkboxes"
    
    # 파일 업로드
    if '파일' in text or '업로드' in text or '첨부' in text:
        return "file_uploads"
    
    # 입력 필드 (큰 영역)
    if area > 5000 or width > 300:
        return "text_inputs"
    
    # 라벨/설명 (작고 긴 텍스트)
    if area < 2000 and len(text) > 3:
        return "labels"
    
    return "unknown"


def _calculate_statistics(elements: List[Dict]) -> Dict[str, Any]:
    """통계 정보 계산"""
    by_type = defaultdict(int)
    for elem in elements:
        by_type[elem['type']] += 1
    
    # 공간 분포
    x_coords = [e['position']['x'] for e in elements]
    y_coords = [e['position']['y'] for e in elements]
    
    spatial = {
        "x_range": {"min": min(x_coords) if x_coords else 0, "max": max(x_coords) if x_coords else 0},
        "y_range": {"min": min(y_coords) if y_coords else 0, "max": max(y_coords) if y_coords else 0},
        "spread": {
            "horizontal": max(x_coords) - min(x_coords) if x_coords else 0,
            "vertical": max(y_coords) - min(y_coords) if y_coords else 0
        }
    }
    
    return {
        "by_type": dict(by_type),
        "spatial": spatial
    }
