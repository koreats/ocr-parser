import re
from typing import Iterable, Mapping, Any
from rapidfuzz import fuzz, process

BIZNO_PAT = re.compile(r"(\d{3})-?(\d{2})-?(\d{5})")
DATE_PAT  = re.compile(r"(20\d{2})[.\-/년 ]?(0?[1-9]|1[0-2])[.\-/월 ]?(0?[1-9]|[12]\d|3[01])")
MONEY_PAT = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\s*원)?")

def neighbors_text(lines: Iterable[Mapping[str, Any]], key_terms: list[str]) -> list[str]:
    texts = [l.get("text") for l in lines if l.get("text")]
    hits = []
    for t in key_terms:
        m = process.extract(t, texts, scorer=fuzz.partial_ratio, limit=3)
        hits.extend([texts[i[2]] for i in m if i[1] >= 80])
    return hits

def extract_invoice_fields(ocr_lines: list[dict]) -> dict:
    text_all = "\n".join([l.get("text","") for l in ocr_lines if l.get("text")])

    bizno = None
    m = BIZNO_PAT.search(text_all)
    if m: bizno = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    date = None
    md = DATE_PAT.search(text_all)
    if md: date = f"{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}"

    money_vals = [int(x.replace(",","")) for x in MONEY_PAT.findall(text_all)]
    total = max(money_vals) if money_vals else None

    near_vat = neighbors_text(ocr_lines, ["부가세", "VAT", "세액"])
    vat = None
    for frag in near_vat:
        m2 = MONEY_PAT.search(frag or "")
        if m2:
            vat = int(m2.group(1).replace(",",""))
            break

    near_supplier = neighbors_text(ocr_lines, ["공급자", "상호", "사업자"])
    supplier = near_supplier[0] if near_supplier else None

    near_buyer = neighbors_text(ocr_lines, ["공급받는자", "수취인", "매입자"])
    buyer = near_buyer[0] if near_buyer else None

    return {
        "supplier": supplier, 
        "bizno": bizno, 
        "date": date, 
        "total": total, 
        "vat": vat, 
        "buyer": buyer
    }
