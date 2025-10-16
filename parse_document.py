import argparse, json, sys, logging
from src.pipeline import parse_document

def setup_logging(level: str = "INFO"):
    """로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

def main():
    ap = argparse.ArgumentParser(description="범용 양식 문서 파서")
    ap.add_argument("--input", required=True, help="입력 파일 경로 (이미지 또는 PDF)")
    ap.add_argument("--form-analysis", action="store_true", default=True, help="양식 구조 분석 활성화")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"], help="로그 레벨")
    ap.add_argument("--output", help="결과 저장 경로 (선택)")
    args = ap.parse_args()
    
    setup_logging(args.log_level)
    
    res = parse_document(args.input, use_form_analysis=args.form_analysis)
    
    output = json.dumps(res, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ 결과 저장: {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    sys.exit(main() or 0)