from src.pipeline import parse_document

def test_parse_smoke_png():
    out = parse_document("tests/sample.png", use_rules_kie=True)
    assert "fields" in out and isinstance(out["fields"], dict)