from typing import Any, List, Dict
from pathlib import Path
from PIL import Image
from .table_normalize import pp_table_to_html_csv

class SuryaLayoutWrapper:
    """PaddlePaddle PPStructure 대체 - Surya Layout + Table Recognition 사용"""
    
    def __init__(self, **kwargs):
        from surya.foundation import FoundationPredictor
        from surya.layout import LayoutPredictor
        from surya.table_rec import TableRecPredictor
        
        # Foundation predictor 초기화
        self.foundation_predictor = FoundationPredictor()
        
        # LayoutPredictor는 foundation_predictor 필요
        self.layout_predictor = LayoutPredictor(self.foundation_predictor)
        
        # TableRecPredictor는 인자 없이 초기화
        self.table_predictor = TableRecPredictor()
    
    def predict(self, input_path: str) -> List[Dict[str, Any]]:
        """Layout 및 Table 감지"""
        image = Image.open(input_path)
        
        # Layout 분석
        layout_predictions = self.layout_predictor([image])
        
        # Table 감지
        table_predictions = self.table_predictor([image])
        
        results = []
        base = Path(input_path).stem
        
        for layout_pred, table_pred in zip(layout_predictions, table_predictions):
            tables = self._convert_tables(table_pred)
            ex = pp_table_to_html_csv(tables, base_name=base)
            
            result = {
                "layout": self._convert_layout(layout_pred),
                "tables": tables,
                "exports": ex,
                "markdown": "",
                "texts": [],
            }
            results.append(result)
        
        return results
    
    def _convert_layout(self, layout_pred):
        """Layout 결과를 원본 가이드 형식으로 변환"""
        layout_boxes = []
        for bbox_info in layout_pred.bboxes:
            layout_boxes.append({
                "bbox": bbox_info.bbox,
                "polygon": bbox_info.polygon,
                "label": bbox_info.label,
                "position": bbox_info.position,
                "confidence": bbox_info.top_k,
            })
        return layout_boxes
    
    def _convert_tables(self, table_pred):
        """Table 결과를 원본 가이드 형식으로 변환"""
        if not hasattr(table_pred, 'rows'):
            return []
        
        tables = [{
            "rows": [
                {
                    "bbox": r.bbox, 
                    "row_id": r.row_id, 
                    "is_header": r.is_header
                } for r in table_pred.rows
            ],
            "cols": [
                {
                    "bbox": c.bbox, 
                    "col_id": c.col_id, 
                    "is_header": c.is_header
                } for c in table_pred.cols
            ],
            "cells": [
                {
                    "bbox": cell.bbox,
                    "text": getattr(cell, "text", ""),
                    "row": cell.row_id,
                    "col": cell.col_id,
                    "rowspan": cell.rowspan,
                    "colspan": cell.colspan,
                } for cell in table_pred.cells
            ],
        }]
        return tables


# 하위 호환성을 위한 alias (PPStructWrapper → SuryaLayoutWrapper)
PPStructWrapper = SuryaLayoutWrapper
