"""
계층적 하이브리드 전략 (3-Level Information Architecture)
LLM에게 양식 구조를 인간이 공간을 설명하는 방식으로 전달
"""
from __future__ import annotations
from typing import List, Dict, Tuple
import numpy as np
from collections import defaultdict

class LayeredFormDescriber:
    """계층적 정보 제공: 전체 → 섹션 → 요소"""
    
    def __init__(self, doc_width: int, doc_height: int):
        self.width = doc_width
        self.height = doc_height
    
    def describe_for_llm(self, elements: List[Dict], ocr_lines: List[Dict]) -> str:
        """
        LLM을 위한 계층적 설명 생성
        Level 1 → Level 2 → Level 3 순서
        """
        if not elements:
            return "# Empty Document\nNo interactive elements found."
        
        sections = self._detect_sections(elements)
        
        output = []
        
        # ===== LEVEL 1: 전체 개요 =====
        output.append(self._level1_overview(elements, sections))
        
        # ===== LEVEL 2: 섹션별 상세 =====
        for section in sections:
            output.append(self._level2_section(section, elements))

        # ===== 모든 OCR 텍스트 추가 =====
        ocr_text_section = ["\n---\n\n## Complete Text Content (OCR)\n", "All text extracted from the document in reading order:\n"]
        for i, line in enumerate(ocr_lines, 1):
            text = line.get('text', '').strip()
            if text:
                bbox = line.get('bbox', [0, 0, 0, 0])
                x, y = bbox[0] if len(bbox) > 0 else 0, bbox[1] if len(bbox) > 1 else 0
                ocr_text_section.append(f"{i}. \"{text}\" — Position: ({x}, {y})")
        output.append("\n".join(ocr_text_section))
        
        # ===== LEVEL 3: 요소별 디테일 (복잡한 경우만) =====
        complex_elements = self._identify_complex_elements(elements)
        if complex_elements:
            output.append("\n---\n\n## Detailed Element Information (Complex Cases Only)\n")
            for elem in complex_elements:
                output.append(self._level3_element(elem, elements))
        
        return "\n\n".join(output)
    
    def _level1_overview(self, elements: List[Dict], sections: List[Dict]) -> str:
        """Level 1: 전체 구조 개요"""
        total_steps = len(elements)
        y_positions = [e['position']['y'] for e in elements]
        
        # 요소 타입별 분포
        type_dist = defaultdict(int)
        for elem in elements:
            type_dist[elem.get('type', 'unknown')] += 1
        
        type_summary = "\n".join([f"  - {k}: {v} elements" for k, v in sorted(type_dist.items())])
        
        aspect_ratio = self.height / self.width
        layout_type = "vertical (portrait)" if aspect_ratio > 1.2 else "horizontal (landscape)" if aspect_ratio < 0.8 else "square"
        
        section_summary = "\n".join([
            f"  {i+1}. {s['name']}: Y {s['y_start']}px - {s['y_end']}px "
            f"({s['y_start']/self.height*100:.0f}%-{s['y_end']/self.height*100:.0f}%)"
            for i, s in enumerate(sections)
        ])
        
        return f"""# How to Use This Prompt

This document structure analysis provides a comprehensive map of a form/document for automated processing or LLM-assisted form filling.

## Suggested Use Cases

1. **Form Auto-Fill**: Use element positions and types to automatically populate fields
2. **Form Understanding**: Identify required fields, sections, and workflow
3. **Data Extraction**: Map where specific information appears in the document
4. **UI Automation**: Generate selenium/playwright scripts based on element locations
5. **Accessibility Analysis**: Understand form structure for screen readers

## How to Interpret This Data

- **Sections**: The form is divided into vertical regions (Section_1, Section_2, etc.)
- **Element Types**: 
  - `labels`: Text descriptions (usually next to input fields)
  - `text_inputs`: Fields where users enter text
  - `checkboxes`: Boolean selection options
  - `buttons`: Action triggers (submit, save, delete, etc.)
  - `file_uploads`: File attachment fields
  - `unknown`: Elements that don't fit other categories
- **Spatial Layout (ASCII)**: Visual representation using symbols:
  - `·` = label
  - `■` = text input
  - `☐` = checkbox
  - `●` = button
  - `⬆` = file upload
  - `?` = unknown
- **Spatial Groupings**: Elements that are visually aligned (vertical clusters, horizontal rows)
- **Detailed Element Info**: For complex elements, includes precise location, size, nearest neighbors, and interaction context

## Typical Workflow

1. Read "Document Structure Overview" to understand form dimensions and element distribution
2. Scan each section to identify the form's logical structure
3. Use "Detailed Element Information" to understand relationships between elements
4. Map your data/task to the appropriate fields based on labels and positions

---

# Document Structure Overview

**Dimensions:** {self.width}px × {self.height}px (aspect ratio {aspect_ratio:.1f}:1 - {layout_type})

**Total Interactive Elements:** {total_steps}

**Element Type Distribution:**
{type_summary}

**Major Sections:** {len(sections)} distinct vertical regions
{section_summary}

**Visual Flow:** Top-to-bottom progression (typical web form pattern)
**Y-axis Range:** {min(y_positions)}px to {max(y_positions)}px"""
    
    def _level2_section(self, section: Dict, all_elements: List[Dict]) -> str:
        """Level 2: 섹션 내부 레이아웃"""
        section_elements = [
            e for e in all_elements 
            if section['y_start'] <= e['position']['y'] <= section['y_end']
        ]
        
        if not section_elements:
            return f"## Section: {section['name']}\n\n**Empty section**"
        
        # 섹션 내 요소 타입 분포
        type_dist = defaultdict(int)
        for e in section_elements:
            type_dist[e.get('type', 'unknown')] += 1
        
        type_composition = "\n".join([f"  - {t}: {c} elements" for t, c in sorted(type_dist.items())])
        
        # ASCII 맵 생성
        ascii_map = self._generate_ascii_map(section, section_elements)
        
        # 공간적 그룹 감지
        spatial_groups = self._detect_spatial_groups(section_elements)
        group_desc = "\n".join([self._describe_group(g) for g in spatial_groups]) if spatial_groups else "  - No clear spatial groupings detected"
        
        return f"""## Section: {section['name']}

**Vertical Range:** Y: {section['y_start']}px - {section['y_end']}px ({section['y_end']-section['y_start']}px tall)
**Position in Document:** {section['y_start']/self.height*100:.0f}% - {section['y_end']/self.height*100:.0f}% from top
**Element Count:** {len(section_elements)} elements

**Element Composition:**
{type_composition}

**Spatial Layout (ASCII Visualization):**
```
{ascii_map}
```

**Spatial Groupings:**
{group_desc}"""
    
    def _level3_element(self, elem: Dict, all_elements: List[Dict]) -> str:
        """Level 3: 개별 요소 상세 (복잡한 경우만)"""
        # 근처 요소 찾기
        nearby = self._find_nearby_elements(elem, all_elements, k=3)
        
        # 정렬된 요소 찾기
        aligned = self._find_aligned_elements(elem, all_elements)
        
        nearby_desc = "\n".join([
            f"  - {n['direction'].capitalize()} {n['distance']}px: Step {n['step']} \"{n['label']}\""
            for n in nearby
        ])
        
        aligned_desc = "\n".join([
            f"  - Step {a['step']} ({a['axis']} axis alignment)"
            for a in aligned
        ]) if aligned else "  - No significant alignments"
        
        interaction_hint = self._infer_interaction_pattern(elem, nearby, aligned)
        
        return f"""### Step {elem['step']}: \"{elem['label']}\"\n
**Precise Location:**
  - Absolute: ({elem['position']['x']}px, {elem['position']['y']}px)
  - Relative: (H: {elem['position']['x']/self.width*100:.1f}%, V: {elem['position']['y']/self.height*100:.1f}%)
  - Zone: {self._classify_zone(elem)}

**Size & Visual Weight:**
  - Dimensions: {elem['width']}px × {elem['height']}px
  - Area: {elem['width']*elem['height']}px² ({"large" if elem['width']*elem['height'] > 5000 else "medium" if elem['width']*elem['height'] > 1000 else "small"})
  - Importance: {self._assess_importance(elem)}

**Spatial Relationships:**
  Nearest Elements:
{nearby_desc}

  Alignments:
{aligned_desc}

**Interaction Context:**
  {interaction_hint}"""
    
    def _detect_sections(self, elements: List[Dict]) -> List[Dict]:
        """Y축 공백 기반 섹션 자동 감지"""
        y_coords = sorted(set([e['position']['y'] for e in elements]))
        
        if len(y_coords) <= 1:
            return [{"y_start": y_coords[0] if y_coords else 0, "y_end": y_coords[0] if y_coords else 0, "name": "Single Section"}]
        
        sections = []
        current_section_start = y_coords[0]
        section_threshold = 100  # 100px 이상 간격이면 섹션 구분
        
        for i in range(1, len(y_coords)):
            gap = y_coords[i] - y_coords[i-1]
            if gap > section_threshold:
                sections.append({
                    "y_start": current_section_start,
                    "y_end": y_coords[i-1],
                    "name": f"Section_{len(sections)+1}"
                })
                current_section_start = y_coords[i]
        
        # 마지막 섹션
        sections.append({
            "y_start": current_section_start,
            "y_end": y_coords[-1],
            "name": f"Section_{len(sections)+1}"
        })
        
        return sections
    
    def _generate_ascii_map(self, section: Dict, elements: List[Dict]) -> str:
        """섹션 내부 ASCII 레이아웃 생성"""
        width_chars = 50
        height_chars = 15
        
        # 캔버스 초기화
        canvas = [[' ' for _ in range(width_chars)] for _ in range(height_chars)]
        
        section_height = section['y_end'] - section['y_start']
        if section_height == 0:
            section_height = 1
        
        for elem in elements:
            try:
                x_char = int((elem['position']['x'] / self.width) * (width_chars - 1))
                y_offset = elem['position']['y'] - section['y_start']
                y_char = int((y_offset / section_height) * (height_chars - 1))
                
                x_char = max(0, min(x_char, width_chars - 1))
                y_char = max(0, min(y_char, height_chars - 1))
                
                symbol = self._get_symbol(elem.get('type', 'unknown'))
                canvas[y_char][x_char] = symbol
            except (ZeroDivisionError, KeyError):
                continue
        
        return '\n'.join([''.join(row) for row in canvas])
    
    def _get_symbol(self, elem_type: str) -> str:
        """요소 타입별 ASCII 심볼"""
        symbols = {
            'text_inputs': '■',
            'buttons': '●',
            'checkboxes': '☐',
            'file_uploads': '⬆',
            'labels': '·',
            'unknown': '?'
        }
        return symbols.get(elem_type, '·')
    
    def _detect_spatial_groups(self, elements: List[Dict]) -> List[Dict]:
        """공간적으로 가까운 요소 그룹 감지"""
        if len(elements) < 2:
            return []
        
        groups = []
        
        # 수직 정렬 그룹 (같은 X 좌표)
        x_groups = defaultdict(list)
        for elem in elements:
            x_rounded = round(elem['position']['x'] / 10) * 10  # 10px 단위로 반올림
            x_groups[x_rounded].append(elem)
        
        for x, group in x_groups.items():
            if len(group) >= 2:
                steps = [e['step'] for e in sorted(group, key=lambda e: e['position']['y'])]
                groups.append({
                    "type": "vertical",
                    "alignment": "left" if x < self.width * 0.3 else "center" if x < self.width * 0.7 else "right",
                    "steps": steps
                })
        
        # 수평 정렬 그룹 (같은 Y 좌표)
        y_groups = defaultdict(list)
        for elem in elements:
            y_rounded = round(elem['position']['y'] / 10) * 10
            y_groups[y_rounded].append(elem)
        
        for y, group in y_groups.items():
            if len(group) >= 2:
                steps = [e['step'] for e in sorted(group, key=lambda e: e['position']['x'])]
                groups.append({
                    "type": "horizontal",
                    "y_position": y,
                    "steps": steps
                })
        
        return groups
    
    def _describe_group(self, group: Dict) -> str:
        """그룹 설명 생성"""
        steps = ", ".join([f"Step {s}" for s in group['steps']])
        
        if group['type'] == 'vertical':
            return f"  - Vertical cluster ({group['alignment']}-aligned): {steps}"
        elif group['type'] == 'horizontal':
            return f"  - Horizontal row (Y: {group['y_position']}px): {steps}"
        return ""
    
    def _find_nearby_elements(self, target: Dict, all_elements: List[Dict], k: int = 3) -> List[Dict]:
        """가장 가까운 k개 요소 찾기"""
        distances = []
        target_x = target['position']['x']
        target_y = target['position']['y']
        
        for elem in all_elements:
            if elem['step'] == target['step']:
                continue
            
            dx = elem['position']['x'] - target_x
            dy = elem['position']['y'] - target_y
            dist = np.sqrt(dx**2 + dy**2)
            
            direction = self._get_direction(dx, dy)
            
            distances.append({
                "step": elem['step'],
                "label": elem['label'],
                "distance": int(dist),
                "direction": direction
            })
        
        return sorted(distances, key=lambda x: x['distance'])[:k]
    
    def _get_direction(self, dx: float, dy: float) -> str:
        """방향 판단 (8방향)"""
        if abs(dy) > abs(dx) * 2:  # 거의 수직
            return "below" if dy > 0 else "above"
        elif abs(dx) > abs(dy) * 2:  # 거의 수평
            return "right" if dx > 0 else "left"
        else:  # 대각선
            v = "below" if dy > 0 else "above"
            h = "right" if dx > 0 else "left"
            return f"{v}-{h}"
    
    def _find_aligned_elements(self, target: Dict, all_elements: List[Dict], threshold: int = 15) -> List[Dict]:
        """정렬된 요소 찾기 (threshold 픽셀 이내)"""
        aligned = []
        target_x = target['position']['x']
        target_y = target['position']['y']
        
        for elem in all_elements:
            if elem['step'] == target['step']:
                continue
            
            # 수직 정렬 (X 좌표 유사)
            if abs(elem['position']['x'] - target_x) < threshold:
                aligned.append({"step": elem['step'], "axis": "vertical"})
            
            # 수평 정렬 (Y 좌표 유사)
            elif abs(elem['position']['y'] - target_y) < threshold:
                aligned.append({"step": elem['step'], "axis": "horizontal"})
        
        return aligned[:5]  # 최대 5개
    
    def _classify_zone(self, elem: Dict) -> str:
        """9분할 영역 분류"""
        x_pct = elem['position']['x'] / self.width
        y_pct = elem['position']['y'] / self.height
        
        h_zone = "left" if x_pct < 0.33 else "center" if x_pct < 0.67 else "right"
        v_zone = "top" if y_pct < 0.33 else "middle" if y_pct < 0.67 else "bottom"
        
        return f"{v_zone}-{h_zone}"
    
    def _assess_importance(self, elem: Dict) -> str:
        """요소 중요도 평가"""
        area = elem['width'] * elem['height']
        elem_type = elem.get('type', '')
        
        # 크기 기반
        if area > 10000:
            size_importance = "high"
        elif area > 2000:
            size_importance = "medium"
        else:
            size_importance = "low"
        
        # 타입 기반
        if elem_type in ['buttons', 'file_uploads']:
            type_importance = "high"
        elif elem_type == 'text_inputs':
            type_importance = "medium"
        else:
            type_importance = "low"
        
        # 위치 기반 (우측 상단/하단은 중요)
        x_pct = elem['position']['x'] / self.width
        y_pct = elem['position']['y'] / self.height
        if x_pct > 0.7 and (y_pct < 0.2 or y_pct > 0.8):
            position_importance = "high"
        else:
            position_importance = "medium"
        
        # 종합
        importance_score = {"high": 3, "medium": 2, "low": 1}
        total = importance_score[size_importance] + importance_score[type_importance] + importance_score[position_importance]
        
        if total >= 8:
            return "critical"
        elif total >= 6:
            return "high"
        elif total >= 4:
            return "medium"
        else:
            return "low"
    
    def _infer_interaction_pattern(self, elem: Dict, nearby: List[Dict], aligned: List[Dict]) -> str:
        """상호작용 패턴 추론"""
        hints = []
        
        # 근처에 버튼이 있으면
        button_nearby = any('버튼' in n['label'] or '등록' in n['label'] or '삭제' in n['label'] for n in nearby)
        if button_nearby:
            hints.append("Likely associated with nearby action button")
        
        # 수직 정렬되면
        vertical_aligned = any(a['axis'] == 'vertical' for a in aligned)
        if vertical_aligned:
            hints.append("Part of a vertical form group")
        
        # 수평 정렬되면
        horizontal_aligned = any(a['axis'] == 'horizontal' for a in aligned)
        if horizontal_aligned:
            hints.append("Part of a horizontal control row")
        
        # 우측 끝이면
        if elem['position']['x'] / self.width > 0.75:
            hints.append("Right-edge positioning - typically for actions/buttons")
        
        # 좌측 끝이면
        if elem['position']['x'] / self.width < 0.25:
            hints.append("Left-edge positioning - typically for labels/inputs")
        
        return " | ".join(hints) if hints else "Standard form element without special context"
    
    def _identify_complex_elements(self, elements: List[Dict]) -> List[Dict]:
        """복잡한 요소 식별 (Level 3에 포함할 요소)"""
        complex = []
        
        for elem in elements:
            # 버튼은 항상 중요
            if elem.get('type') == 'buttons':
                complex.append(elem)
            # 파일 업로드도 중요
            elif elem.get('type') == 'file_uploads':
                complex.append(elem)
            # 큰 입력 필드
            elif elem.get('type') == 'text_inputs' and elem['width'] * elem['height'] > 5000:
                complex.append(elem)
            # 우측 상단/하단 요소
            elif (elem['position']['x'] / self.width > 0.7 and 
                  (elem['position']['y'] / self.height < 0.2 or elem['position']['y'] / self.height > 0.8)):
                complex.append(elem)
        
        # 최대 10개만 (토큰 절약)
        return sorted(complex, key=lambda e: self._assess_importance(e), reverse=True)[:10]
