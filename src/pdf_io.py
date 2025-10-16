from pathlib import Path
import fitz  # PyMuPDF

def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Path]:
    p = Path(pdf_path)
    doc = fitz.open(p.as_posix())
    outs: list[Path] = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        out = p.with_suffix(f".page{i+1:03d}.png")
        pix.save(out.as_posix())
        outs.append(out)
    doc.close()
    return outs