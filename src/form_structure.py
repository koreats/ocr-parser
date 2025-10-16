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

def extract_form_structure(ocr_lines: list[dict], layout_data: list[dict]) -> dict:
    """
    OCR 결과와 PP-Structure로부터 양식 구조 분석 (개선된 label 추출)
    """
    pp_structure = layout_data
    # 기본 구조
    structure = {
        "title": "",
        "sections": [],
        "form_elements": {
            "text_inputs": [],
            "checkboxes": [],
            "buttons": [],
            "file_uploads": []
        },
        "tables": []
    }
    
    if not ocr_lines:
        return structure
    
    # 1. 문서 제목 추출 (첫 번째 큰 텍스트)
    sorted_lines = sorted(ocr_lines, key=lambda x: x.get("bbox", [0,0,0,0])[1])
    for line in sorted_lines[:5]:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        height = bbox[3] - bbox[1]
        
        if text and height > 20:
            structure["title"] = text
            break
    
    if not structure["title"] and sorted_lines:
        structure["title"] = sorted_lines[0].get("text", "").strip()
    
    # 2. 섹션 분석 (큰 텍스트를 섹션으로)
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        
        if not text or not bbox:
            continue
        
        height = bbox[3] - bbox[1]
        
        # 섹션 제목 조건: 높이 > 15 또는 특정 키워드
        is_section = (
            height > 15 or
            any(keyword in text for keyword in ["사건", "내용", "서류", "정보", "항목", "입력", "제출"])
        )
        
        if is_section and len(text) > 3:
            structure["sections"].append({
                "title": text,
                "content": "",
                "bbox": bbox
            })
    
    # 3. 양식 요소 감지 (개선된 label 추출)
    
    # 텍스트 입력 필드 감지
    text_input_keywords = ["입력", "작성", "기재", "*", "필수", "선택", "내용"]
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        
        if not text or not bbox:
            continue
        
        # 입력 필드 감지 조건
        is_input = (
            any(keyword in text for keyword in text_input_keywords) or
            "*" in text or
            ":" in text or
            "①" in text or
            "_" in text or
            (bbox[2] - bbox[0]) > 200  # 넓은 영역
        )
        
        if is_input:
            # label 정제 (특수문자 제거)
            label = text.replace("*", "").replace("①", "").replace(":", "").strip()
            
            structure["form_elements"]["text_inputs"].append({
                "text": label,
                "bbox": bbox
            })
    
    # 체크박스 감지
    checkbox_keywords = ["✓", "☑", "□", "선택", "동의", "확인"]
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        
        if not text or not bbox:
            continue
        
        is_checkbox = any(keyword in text for keyword in checkbox_keywords)
        
        if is_checkbox:
            label = text.replace("✓", "").replace("☑", "").replace("□", "").strip()
            structure["form_elements"]["checkboxes"].append({
                "text": label,
                "bbox": bbox
            })
    
    # 버튼 감지
    button_keywords = ["등록", "제출", "저장", "완료", "취소", "삭제", "추가", "조회", "검색", "찾기", "선택"]
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        
        if not text or not bbox:
            continue
        
        is_button = (
            any(keyword in text for keyword in button_keywords) and
            len(text) <= 20  # 버튼은 보통 짧음
        )
        
        if is_button:
            structure["form_elements"]["buttons"].append({
                "text": text,
                "bbox": bbox
            })
    
    # 파일 업로드 감지
    file_keywords = ["파일", "첨부", "업로드", "찾기", "DRAG", "DROP"]
    for line in ocr_lines:
        text = line.get("text", "").strip()
        bbox = line.get("bbox", [0, 0, 0, 0])
        
        if not text or not bbox:
            continue
        
        is_file_upload = any(keyword in text for keyword in file_keywords)
        
        if is_file_upload:
            label = text
            structure["form_elements"]["file_uploads"].append({
                "text": label,
                "bbox": bbox
            })
    
    # 4. 표 정보 추출
    for pp_res in pp_structure:
        tables = pp_res.get("tables", [])
        for table in tables:
            cells = table.get("cells", [])
            if not cells:
                continue
            
            max_row = max([c.get("row", 0) for c in cells], default=0)
            max_col = max([c.get("col", 0) for c in cells], default=0)
            
            structure["tables"].append({
                "rows": max_row + 1,
                "columns": max_col + 1,
                "bbox": table.get("bbox")
            })
    
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
            prompt_parts.append(f"{i}. {section['title']}")
            if section.get('content'):
                content = section['content'] if isinstance(section['content'], str) else ' / '.join(section['content'][:3])
                prompt_parts.append(f"   내용: {content}")
    
    # 양식 요소
    elements = form_structure['form_elements']
    
    if elements['text_inputs']:
        prompt_parts.append(f"\n## 텍스트 입력 필드 ({len(elements['text_inputs'])}개):")
        for inp in elements['text_inputs'][:5]:
            req = "[필수]" if inp.get('required') else ""
            label = inp.get('text', inp.get('label', ''))
            prompt_parts.append(f"- {req} {label}")
    
    if elements['checkboxes']:
        prompt_parts.append(f"\n## 체크박스 ({len(elements['checkboxes'])}개):")
        for cb in elements['checkboxes'][:5]:
            label = cb.get('text', cb.get('label', ''))
            prompt_parts.append(f"- {label}")
    
    if elements['buttons']:
        prompt_parts.append(f"\n## 버튼 ({len(elements['buttons'])}개):")
        for btn in elements['buttons']:
            label = btn.get('text', btn.get('label', ''))
            action = btn.get('action', 'unknown')
            prompt_parts.append(f"- {label} (동작: {action})")
    
    if elements['file_uploads']:
        prompt_parts.append(f"\n## 파일 업로드 ({len(elements['file_uploads'])}개):")
        for upload in elements['file_uploads']:
            label = upload.get('text', upload.get('label', ''))
            prompt_parts.append(f"- {label}")
    
    # 표 정보
    if form_structure['tables']:
        prompt_parts.append(f"\n## 표 정보 ({len(form_structure['tables'])}개):")
        for i, table in enumerate(form_structure['tables'], 1):
            rows = table.get('rows', 0)
            cols = table.get('columns', table.get('cols', 0))
            cells = rows * cols
            prompt_parts.append(f"{i}. {rows}행 x {cols}열 (총 {cells}개 셀)")
    
    return "\n".join(prompt_parts)

def generate_json_prompt(ocr_lines: list[dict], form_structure: dict) -> dict:
    """
    LLM이 단계별 가이드를 제공할 수 있도록 구조화된 JSON 프롬프트 생성
    각 요소의 위치, 타입, 순서를 포함
    """
    json_prompt = {
        "document_info": {
            "title": form_structure.get("title", ""),
            "total_sections": len(form_structure.get("sections", [])),
            "total_elements": sum([
                len(form_structure.get("form_elements", {}).get("text_inputs", [])),
                len(form_structure.get("form_elements", {}).get("checkboxes", [])),
                len(form_structure.get("form_elements", {}).get("buttons", [])),
                len(form_structure.get("form_elements", {}).get("file_uploads", []))
            ]),
            "page_dimensions": {
                "width": max([line.get("bbox", [0,0,0,0])[2] for line in ocr_lines if line.get("bbox")], default=1920),
                "height": max([line.get("bbox", [0,0,0,0])[3] for line in ocr_lines if line.get("bbox")], default=1080)
            }
        },
        "sections": [],
        "form_elements": [],
        "tables": [],
        "interaction_steps": []
    }
    
    step_order = 1
    
    # 섹션 정보
    for idx, section in enumerate(form_structure.get("sections", []), 1):
        section_data = {
            "id": f"section_{idx}",
            "order": idx,
            "title": section.get("title", ""),
            "content": section.get("content", ""),
            "bbox": section.get("bbox")
        }
        json_prompt["sections"].append(section_data)
    
    # 텍스트 입력 필드
    for idx, text_input in enumerate(form_structure.get("form_elements", {}).get("text_inputs", []), 1):
        element = {
            "id": f"input_{idx}",
            "type": "text_input",
            "step_order": step_order,
            "label": text_input.get("text", ""),
            "required": "[필수]" in text_input.get("text", "") or "*" in text_input.get("text", ""),
            "position": {
                "x": text_input.get("bbox", [0,0,0,0])[0],
                "y": text_input.get("bbox", [0,0,0,0])[1],
                "width": text_input.get("bbox", [0,0,0,0])[2] - text_input.get("bbox", [0,0,0,0])[0],
                "height": text_input.get("bbox", [0,0,0,0])[3] - text_input.get("bbox", [0,0,0,0])[1]
            } if text_input.get("bbox") else None,
            "attributes": {
                "placeholder": "입력하세요" if "입력" in text_input.get("text", "") else "",
                "max_length": _extract_max_length(text_input.get("text", "")),
                "multiline": "여러" in text_input.get("text", "") or "이내" in text_input.get("text", "")
            }
        }
        json_prompt["form_elements"].append(element)
        
        # 상호작용 단계 추가
        json_prompt["interaction_steps"].append({
            "step": step_order,
            "action": "input_text",
            "target_id": element["id"],
            "instruction": f"'{element['label']}' 입력란을 찾아 텍스트를 입력하세요.",
            "position": element["position"],
            "required": element["required"]
        })
        step_order += 1
    
    # 체크박스
    for idx, checkbox in enumerate(form_structure.get("form_elements", {}).get("checkboxes", []), 1):
        element = {
            "id": f"checkbox_{idx}",
            "type": "checkbox",
            "step_order": step_order,
            "label": checkbox.get("text", ""),
            "position": {
                "x": checkbox.get("bbox", [0,0,0,0])[0],
                "y": checkbox.get("bbox", [0,0,0,0])[1],
                "width": checkbox.get("bbox", [0,0,0,0])[2] - checkbox.get("bbox", [0,0,0,0])[0],
                "height": checkbox.get("bbox", [0,0,0,0])[3] - checkbox.get("bbox", [0,0,0,0])[1]
            } if checkbox.get("bbox") else None,
            "checked": "✓" in checkbox.get("text", "") or "☑" in checkbox.get("text", "")
        }
        json_prompt["form_elements"].append(element)
        
        json_prompt["interaction_steps"].append({
            "step": step_order,
            "action": "check" if element["checked"] else "uncheck",
            "target_id": element["id"],
            "instruction": f"'{element['label']}' 체크박스를 선택하세요.",
            "position": element["position"]
        })
        step_order += 1
    
    # 버튼
    for idx, button in enumerate(form_structure.get("form_elements", {}).get("buttons", []), 1):
        button_action = _classify_button_action(button.get("text", ""))
        
        element = {
            "id": f"button_{idx}",
            "type": "button",
            "step_order": step_order,
            "label": button.get("text", ""),
            "action": button_action,
            "position": {
                "x": button.get("bbox", [0,0,0,0])[0],
                "y": button.get("bbox", [0,0,0,0])[1],
                "width": button.get("bbox", [0,0,0,0])[2] - button.get("bbox", [0,0,0,0])[0],
                "height": button.get("bbox", [0,0,0,0])[3] - button.get("bbox", [0,0,0,0])[1]
            } if button.get("bbox") else None,
            "importance": "high" if button_action in ["submit", "complete"] else "medium"
        }
        json_prompt["form_elements"].append(element)
        
        # 제출/완료 버튼만 상호작용 단계에 추가
        if button_action in ["submit", "complete", "save"]:
            json_prompt["interaction_steps"].append({
                "step": step_order,
                "action": "click_button",
                "target_id": element["id"],
                "instruction": f"'{element['label']}' 버튼을 클릭하여 {button_action}하세요.",
                "position": element["position"],
                "importance": element["importance"]
            })
            step_order += 1
    
    # 파일 업로드
    for idx, file_upload in enumerate(form_structure.get("form_elements", {}).get("file_uploads", []), 1):
        element = {
            "id": f"file_{idx}",
            "type": "file_upload",
            "step_order": step_order,
            "label": file_upload.get("text", ""),
            "position": {
                "x": file_upload.get("bbox", [0,0,0,0])[0],
                "y": file_upload.get("bbox", [0,0,0,0])[1],
                "width": file_upload.get("bbox", [0,0,0,0])[2] - file_upload.get("bbox", [0,0,0,0])[0],
                "height": file_upload.get("bbox", [0,0,0,0])[3] - file_upload.get("bbox", [0,0,0,0])[1]
            } if file_upload.get("bbox") else None,
            "attributes": {
                "accept": "모든 파일" if "모든" in file_upload.get("text", "") else "PDF, 이미지",
                "multiple": "여러" in file_upload.get("text", "") or "다중" in file_upload.get("text", "")
            }
        }
        json_prompt["form_elements"].append(element)
        
        json_prompt["interaction_steps"].append({
            "step": step_order,
            "action": "upload_file",
            "target_id": element["id"],
            "instruction": f"'{element['label']}' 영역에 파일을 업로드하세요.",
            "position": element["position"]
        })
        step_order += 1
    
    # 표 정보
    for idx, table in enumerate(form_structure.get("tables", []), 1):
        table_data = {
            "id": f"table_{idx}",
            "rows": table.get("rows", 0),
            "columns": table.get("columns", 0),
            "total_cells": table.get("rows", 0) * table.get("columns", 0),
            "position": table.get("bbox"),
            "description": f"{table.get('rows', 0)}행 x {table.get('columns', 0)}열 표"
        }
        json_prompt["tables"].append(table_data)
    
    # 상호작용 단계 정렬 (step_order 기준)
    json_prompt["interaction_steps"].sort(key=lambda x: x["step"])
    
    return json_prompt


def _extract_max_length(text: str) -> int | None:
    """텍스트에서 최대 길이 추출 (예: '2000자 이내' -> 2000)"""
    import re
    match = re.search(r'(\d+)자', text)
    return int(match.group(1)) if match else None


def _classify_button_action(text: str) -> str:
    """버튼 텍스트로 액션 분류"""
    text = text.lower()
    if any(word in text for word in ['등록', '제출', '신청', '완료']):
        return 'submit' if '등록' in text or '제출' in text else 'complete'
    elif any(word in text for word in ['저장', 'save']):
        return 'save'
    elif any(word in text for word in ['삭제', 'delete']):
        return 'delete'
    elif any(word in text for word in ['취소', 'cancel']):
        return 'cancel'
    elif any(word in text for word in ['검색', '조회', 'search']):
        return 'search'
    elif any(word in text for word in ['추가', 'add']):
        return 'add'
    else:
        return 'unknown'

def generate_hybrid_prompt(ocr_lines: list[dict], form_structure: dict) -> str:
    """
    Markdown + JSON 하이브리드 프롬프트 생성
    인간 친화적 설명 + 정확한 구조 데이터 조합
    """
    title = form_structure.get("title", "문서")
    sections = form_structure.get("sections", [])
    form_elements = form_structure.get("form_elements", {})
    tables = form_structure.get("tables", [])
    
    # 통계 계산
    total_inputs = len(form_elements.get("text_inputs", []))
    required_inputs = sum(1 for inp in form_elements.get("text_inputs", []) 
                         if "[필수]" in inp.get("text", "") or "*" in inp.get("text", ""))
    total_steps = total_inputs + len(form_elements.get("file_uploads", [])) + 1
    
    # 프롬프트 시작
    prompt = f"""# 📄 문서: {title}

## 📋 전체 개요
- **총 단계:** {total_steps}단계
- **필수 입력:** {required_inputs}개
- **선택 입력:** {total_inputs - required_inputs}개
- **표:** {len(tables)}개
- **예상 소요 시간:** {_estimate_time(total_steps)}분

---

"""
    
    # 단계별 가이드 생성
    step_number = 1
    
    # 텍스트 입력 필드
    for inp in form_elements.get("text_inputs", []):
        label = inp.get("text", "").replace("[필수]", "").strip()
        required = "[필수]" in inp.get("text", "") or "*" in inp.get("text", "")
        bbox = inp.get("bbox", [0, 0, 0, 0])
        max_length = _extract_max_length(inp.get("text", ""))
        
        prompt += f"""## 🔹 {step_number}단계: {label} {"(필수)" if required else "(선택)"}

### 위치 안내
화면 좌표 (X: {bbox[0]:.0f}, Y: {bbox[1]:.0f}) 위치의 입력란

### 작성 가이드
- {"**필수 입력 항목**" if required else "선택 입력 항목"}
{f'- 최대 {max_length}자까지 입력 가능' if max_length else ''}
- 명확하고 정확하게 작성하세요

### 상세 정보 (JSON)
```json
{{
  "step": {step_number},
  "element_id": "input_{step_number}",
  "type": "text_input",
  "label": "{label}",
  "required": {str(required).lower()},
  "position": {{
    "x": {bbox[0]:.0f},
    "y": {bbox[1]:.0f},
    "width": {bbox[2] - bbox[0]:.0f},
    "height": {bbox[3] - bbox[1]:.0f}
  }},
  "attributes": {{
    "max_length": {max_length or "null"},
    "multiline": {str("이내" in inp.get("text", "") or "여러" in inp.get("text", "")).lower()}
  }},
  "validation": {{
    "required": {str(required).lower()}
  }}
}}
```

---

"""
        step_number += 1
    
    # 체크박스
    for idx, checkbox in enumerate(form_elements.get("checkboxes", []), 1):
        label = checkbox.get("text", "").replace("✓", "").replace("☑", "").strip()
        bbox = checkbox.get("bbox", [0, 0, 0, 0])
        checked = "✓" in checkbox.get("text", "") or "☑" in checkbox.get("text", "")
        
        prompt += f"""## 🔹 {step_number}단계: {label} 선택

### 위치 안내
화면 좌표 (X: {bbox[0]:.0f}, Y: {bbox[1]:.0f}) 위치의 체크박스

### 작성 가이드
- {"현재 선택됨" if checked else "선택 필요 시 클릭"}
- 해당 항목에 동의하거나 선택할 경우 체크

### 상세 정보 (JSON)
```json
{{
  "step": {step_number},
  "element_id": "checkbox_{idx}",
  "type": "checkbox",
  "label": "{label}",
  "position": {{
    "x": {bbox[0]:.0f},
    "y": {bbox[1]:.0f}
  }},
  "checked": {str(checked).lower()}
}}
```

---

"""
        step_number += 1
    
    # 파일 업로드
    for idx, file_upload in enumerate(form_elements.get("file_uploads", []), 1):
        label = file_upload.get("text", "")
        bbox = file_upload.get("bbox", [0, 0, 0, 0])
        
        prompt += f"""## 🔹 {step_number}단계: {label}

### 위치 안내
화면 좌표 (X: {bbox[0]:.0f}, Y: {bbox[1]:.0f}) 위치의 파일 업로드 영역

### 작성 가이드
- "파일찾기" 버튼 클릭 또는 드래그 앤 드롭
- PDF, 이미지(JPG, PNG) 지원
- 파일당 최대 10MB 권장

### 상세 정보 (JSON)
```json
{{
  "step": {step_number},
  "element_id": "file_{idx}",
  "type": "file_upload",
  "label": "{label}",
  "position": {{
    "x": {bbox[0]:.0f},
    "y": {bbox[1]:.0f}
  }},
  "attributes": {{
    "accept": [".pdf", ".jpg", ".png"],
    "multiple": {"true" if "여러" in label or "다중" in label else "false"},
    "max_size_mb": 10
  }}
}}
```

---

"""
        step_number += 1
    
    # 제출 버튼 찾기
    submit_buttons = [btn for btn in form_elements.get("buttons", []) 
                     if any(word in btn.get("text", "").lower() 
                           for word in ["완료", "제출", "등록"])]
    
    if submit_buttons:
        btn = submit_buttons[0]
        label = btn.get("text", "")
        bbox = btn.get("bbox", [0, 0, 0, 0])
        
        prompt += f"""## 🔹 최종 단계: {label}

### 위치 안내
화면 좌표 (X: {bbox[0]:.0f}, Y: {bbox[1]:.0f}) 위치의 "{label}" 버튼

### 작성 가이드
- **모든 필수 항목 입력 확인 후 클릭**
- 임시저장 기능이 있다면 먼저 저장 권장
- 제출 후 수정 불가능할 수 있음

### 상세 정보 (JSON)
```json
{{
  "step": {step_number},
  "element_id": "button_submit",
  "type": "button",
  "label": "{label}",
  "action": "submit",
  "position": {{
    "x": {bbox[0]:.0f},
    "y": {bbox[1]:.0f},
    "width": {bbox[2] - bbox[0]:.0f},
    "height": {bbox[3] - bbox[1]:.0f}
  }},
  "importance": "high"
}}
```

---

"""
    
    # 표 정보
    if tables:
        prompt += "\n## 📊 표 정보\n\n"
        for idx, table in enumerate(tables, 1):
            prompt += f"""### 표 {idx}
- **크기:** {table.get('rows', 0)}행 x {table.get('columns', 0)}열
- **총 셀:** {table.get('rows', 0) * table.get('columns', 0)}개
```json
{{
  "table_id": "table_{idx}",
  "rows": {table.get('rows', 0)},
  "columns": {table.get('columns', 0)},
  "total_cells": {table.get('rows', 0) * table.get('columns', 0)}
}}
```

"""
    
    # LLM 작성 가이드
    prompt += """

---

## 💡 LLM 작성 가이드

### 이 프롬프트 사용법
1. **단계별 진행:** 위 단계를 순서대로 따라가세요
2. **JSON 활용:** 각 단계의 JSON 데이터로 정확한 위치 파악
3. **검증:** 필수 항목 누락 여부 확인
4. **사용자 확인:** 불명확한 내용은 사용자에게 질문

### 응답 형식
사용자가 작성 요청 시, 다음 형식으로 안내하세요:
```
[1단계] 변론내용 입력
→ 화면 상단의 큰 입력란에 다음 내용을 입력하세요:
  "..."

[2단계] 입증서류 첨부
→ "파일찾기" 버튼을 클릭하여 증거 문서를 업로드하세요.

...
```
"""
    
    return prompt


def _estimate_time(steps: int) -> int:
    """단계 수로 예상 소요 시간 계산 (분)"""
    return min(max(steps * 2, 5), 30)
