"""
범용 양식 구조 추출 모듈
OCR, Layout, Table 결과를 종합하여 양식의 구조를 파악하고 LLM용 프롬프트를 생성
"""
import re
import logging
from typing import Any, Dict, List
from rapidfuzz import fuzz

log = logging.getLogger(__name__)

# 양식 요소 감지 패턴
CHECKBOX_PATTERNS = [
    r'☐', r'□', r'▢', r'◻', r'✓', r'✔', r'☑', r'✅',
    r' Replaced_Newline ', r' Replaced_Newline '
]
BUTTON_KEYWORDS = ['등록', '조회', '삭제', '저장', '완료', '취소', '찾기', '추가']
INPUT_INDICATORS = ['*', '필수', '입력', '작성', '선택']
FILE_UPLOAD_KEYWORDS = ['파일첨부', '파일찾기', '업로드', 'DRAG & DROP']

def extract_form_structure(ocr_lines: List[Dict], layout_data: List[Dict]) -> Dict[str, Any]:
    """
    OCR 라인과 Layout 데이터를 분석하여 양식 구조 추출
    
    Args:
        ocr_lines: OCR 텍스트 라인 리스트
        layout_data: Layout 분석 결과
    
    Returns:
        구조화된 양식 데이터
    """
    log.info(f"양식 구조 추출 시작: OCR 라인 {len(ocr_lines)}개, Layout {len(layout_data)}개")
    
    structure = {
        "title": _extract_title(ocr_lines),
        "sections": _extract_sections(ocr_lines, layout_data),
        "form_elements": {
            "text_inputs": _find_text_inputs(ocr_lines),
            "checkboxes": _find_checkboxes(ocr_lines),
            "buttons": _find_buttons(ocr_lines),
            "file_uploads": _find_file_uploads(ocr_lines),
            "required_fields": _find_required_fields(ocr_lines)
        },
        "tables": _extract_table_info(layout_data),
        "metadata": {
            "total_ocr_lines": len(ocr_lines),
            "total_layout_elements": len(layout_data)
        }
    }
    
    log.info(f"양식 구조 추출 완료: 제목={structure['title']}, 섹션={len(structure['sections'])}개")
    return structure

def _extract_title(ocr_lines: List[Dict]) -> str:
    """문서 제목 추출 (첫 5줄 중 가장 큰 텍스트 또는 특정 패턴)"""
    if not ocr_lines:
        return ""
    
    # 첫 10줄 중에서 제목 후보 찾기
    candidates = []
    for line in ocr_lines[:10]:
        text = line.get("text", "").strip()
        if not text or len(text) < 2:
            continue
        
        # 제목 패턴: ○, ■, 서식명, 신고서, 신청서 등
        if any(keyword in text for keyword in ['○', '■', '서식', '신고서', '신청서', '준비서면']):
            candidates.append(text)
    
    if candidates:
        return candidates[0]
    
    # 후보가 없으면 첫 줄 반환
    return ocr_lines[0].get("text", "").strip() if ocr_lines else ""

def _extract_sections(ocr_lines: List[Dict], layout_data: List[Dict]) -> List[Dict]:
    """섹션 추출 (사건기본정보, 변론내용 등)"""
    sections = []
    section_keywords = ['정보', '내용', '서류', '입증', '첨부']
    
    current_section = None
    for i, line in enumerate(ocr_lines):
        text = line.get("text", "").strip()
        
        # 섹션 헤더 감지 (특수문자 + 키워드)
        if any(kw in text for kw in section_keywords):
            if current_section:
                sections.append(current_section)
            
            current_section = {
                "name": text,
                "start_line": i,
                "fields": [],
                "content": []
            }
        elif current_section:
            current_section["content"].append(text)
    
    if current_section:
        sections.append(current_section)
    
    log.info(f"추출된 섹션: {[s['name'] for s in sections]}")
    return sections

def _find_text_inputs(ocr_lines: List[Dict]) -> List[Dict]:
    """텍스트 입력 필드 감지"""
    inputs = []
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox")
        
        # 입력 필드 패턴: "*", "필수", "입력하세요"
        if any(indicator in text for indicator in INPUT_INDICATORS):
            inputs.append({
                "label": text,
                "bbox": bbox,
                "required": "*" in text or "필수" in text
            })
    
    log.info(f"텍스트 입력 필드 {len(inputs)}개 감지")
    return inputs

def _find_checkboxes(ocr_lines: List[Dict]) -> List[Dict]:
    """체크박스 감지"""
    checkboxes = []
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox")
        
        # 체크박스 패턴 매칭
        for pattern in CHECKBOX_PATTERNS:
            if re.search(pattern, text):
                checkboxes.append({
                    "label": text,
                    "bbox": bbox,
                    "checked": any(c in text for c in ['✓', '✔', '☑', '✅'])
                })
                break
    
    log.info(f"체크박스 {len(checkboxes)}개 감지")
    return checkboxes

def _find_buttons(ocr_lines: List[Dict]) -> List[Dict]:
    """버튼 감지"""
    buttons = []
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox")
        
        # 버튼 키워드 매칭
        if any(kw in text for kw in BUTTON_KEYWORDS):
            buttons.append({
                "label": text,
                "bbox": bbox,
                "action": _infer_button_action(text)
            })
    
    log.info(f"버튼 {len(buttons)}개 감지")
    return buttons

def _find_file_uploads(ocr_lines: List[Dict]) -> List[Dict]:
    """파일 업로드 필드 감지"""
    uploads = []
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox")
        
        if any(kw in text for kw in FILE_UPLOAD_KEYWORDS):
            uploads.append({
                "label": text,
                "bbox": bbox
            })
    
    log.info(f"파일 업로드 필드 {len(uploads)}개 감지")
    return uploads

def _find_required_fields(ocr_lines: List[Dict]) -> List[str]:
    """필수 입력 필드 추출"""
    required = []
    for line in ocr_lines:
        text = line.get("text", "").strip()
        if "*" in text or "필수" in text:
            required.append(text)
    
    return required

def _infer_button_action(text: str) -> str:
    """버튼의 동작 추론"""
    action_map = {
        "등록": "submit",
        "저장": "save",
        "조회": "search",
        "삭제": "delete",
        "완료": "complete",
        "취소": "cancel"
    }
    
    for keyword, action in action_map.items():
        if keyword in text:
            return action
    
    return "unknown"

def _extract_table_info(layout_data: List[Dict]) -> List[Dict]:
    """표 정보 추출"""
    tables = []
    for layout_item in layout_data:
        for table in layout_item.get("tables", []):
            tables.append({
                "rows": len(table.get("rows", [])),
                "cols": len(table.get("cols", [])),
                "cells": len(table.get("cells", []))
            })
    
    log.info(f"표 {len(tables)}개 감지")
    return tables

def generate_llm_prompt(form_structure: Dict[str, Any]) -> str:
    """
    양식 구조를 LLM이 이해하기 쉬운 프롬프트로 변환
    
    Args:
        form_structure: extract_form_structure()의 결과
    
    Returns:
        LLM용 구조화된 프롬프트
    """
    prompt_parts = []
    
    # 문서 제목
    prompt_parts.append(f"# 문서 제목: {form_structure['title']}\n")
    
    # 섹션 정보
    if form_structure['sections']:
        prompt_parts.append("\n## 문서 섹션:")
        for i, section in enumerate(form_structure['sections'], 1):
            prompt_parts.append(f"{i}. {section['name']}")
            if section['content']:
                prompt_parts.append(f"   내용: {' / '.join(section['content'][:3])}")
    
    # 양식 요소
    elements = form_structure['form_elements']
    
    if elements['text_inputs']:
        prompt_parts.append(f"\n## 텍스트 입력 필드 ({len(elements['text_inputs'])}개):")
        for inp in elements['text_inputs'][:5]:
            req = "[필수]" if inp['required'] else ""
            prompt_parts.append(f"- {req} {inp['label']}")
    
    if elements['checkboxes']:
        prompt_parts.append(f"\n## 체크박스 ({len(elements['checkboxes'])}개):")
        for cb in elements['checkboxes'][:5]:
            prompt_parts.append(f"- {cb['label']}")
    
    if elements['buttons']:
        prompt_parts.append(f"\n## 버튼 ({len(elements['buttons'])}개):")
        for btn in elements['buttons']:
            prompt_parts.append(f"- {btn['label']} (동작: {btn['action']})")
    
    if elements['file_uploads']:
        prompt_parts.append(f"\n## 파일 업로드 ({len(elements['file_uploads'])}개):")
        for upload in elements['file_uploads']:
            prompt_parts.append(f"- {upload['label']}")
    
    # 표 정보
    if form_structure['tables']:
        prompt_parts.append(f"\n## 표 정보 ({len(form_structure['tables'])}개):")
        for i, table in enumerate(form_structure['tables'], 1):
            prompt_parts.append(f"{i}. {table['rows']}행 x {table['cols']}열 (총 {table['cells']}개 셀)")
    
    return "\n".join(prompt_parts)
