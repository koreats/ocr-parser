from __future__ import annotations
from typing import Any, List, Dict
from pathlib import Path
import os
import pandas as pd

def ensure_out():
    Path("out").mkdir(exist_ok=True)

def pp_table_to_html_csv(pp_tables: List[Dict[str, Any]], base_name: str) -> list[dict]:
    """Surya Table 결과를 HTML/CSV로 변환"""
    ensure_out()
    exports = []
    for ti, t in enumerate(pp_tables or []):
        # HTML 생성 (간단한 테이블 구조)
        html_path = f"out/{base_name}.table{ti+1:02d}.html"
        cells = t.get("cells") or []
        
        if cells:
            # 간단한 HTML 테이블 생성
            html_content = "<table border='1'>\n"
            max_row = max([c.get("row", 0) for c in cells], default=0)
            max_col = max([c.get("col", 0) for c in cells], default=0)
            
            for r in range(max_row + 1):
                html_content += "  <tr>\n"
                for c in range(max_col + 1):
                    cell = next((x for x in cells if x.get("row") == r and x.get("col") == c), None)
                    text = cell.get("text", "") if cell else ""
                    rowspan = cell.get("rowspan", 1) if cell else 1
                    colspan = cell.get("colspan", 1) if cell else 1
                    html_content += f'    <td rowspan="{rowspan}" colspan="{colspan}">{text}</td>\n'
                html_content += "  </tr>\n"
            html_content += "</table>"
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        
        # CSV 생성
        max_r = 0
        max_c = 0
        for c in cells:
            r = int(c.get("row", 0)) + max(1, int(c.get("rowspan", 1))) - 1
            cc = int(c.get("col", 0)) + max(1, int(c.get("colspan", 1))) - 1
            max_r = max(max_r, r)
            max_c = max(max_c, cc)
        
        grid = [[None for _ in range(max_c + 1)] for _ in range(max_r + 1)]
        for c in cells:
            r, c0 = int(c.get("row", 0)), int(c.get("col", 0))
            text = (c.get("text") or "").strip()
            if grid[r][c0] is None:
                grid[r][c0] = text
            else:
                grid[r][c0] = f"{grid[r][c0]} {text}"
        
        df = pd.DataFrame(grid)
        csv_path = f"out/{base_name}.table{ti+1:02d}.csv"
        df.to_csv(csv_path, index=False, header=False)
        
        exports.append({
            "html_path": html_path, 
            "csv_path": csv_path, 
            "rows": len(grid), 
            "cols": len(grid[0]) if grid else 0
        })
    
    return exports
