from pathlib import Path
from typing import Any
from PIL import Image

def run_surya_ocr(images: list[Path]) -> list[dict[str, Any]]:
    """Surya-OCR 0.17.0+ API 사용"""
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor
    
    # Predictor 초기화
    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    detection_predictor = DetectionPredictor()
    
    # 이미지 로드
    pil_images = [Image.open(im) for im in images]
    
    # OCR 실행
    predictions = recognition_predictor(pil_images, det_predictor=detection_predictor)
    
    # 결과 변환 (원본 가이드 형식 유지)
    results = []
    for pred in predictions:
        blocks = []
        for line in pred.text_lines:
            blocks.append({
                "type": "text",
                "text": line.text,
                "bbox": line.bbox,
                "polygon": line.polygon,
                "confidence": line.confidence,
                "order": None,
            })
        results.append({"blocks": blocks})
    
    return results