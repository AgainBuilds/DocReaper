from pathlib import Path
from bs4 import BeautifulSoup
from .schemas import DocumentFormat

def extract_bytes(data: bytes, filename: str = "", content_type: str = "") -> tuple[str, DocumentFormat, dict]:
    suffix = Path(filename).suffix.lower()
    ctype = content_type.lower()
    if suffix == ".pdf" or "pdf" in ctype:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        text = "\n".join(page.get_text("text") for page in doc)
        meta = dict(doc.metadata or {})
        doc.close()
        return text, DocumentFormat.PDF, meta
    if suffix == ".docx" or "wordprocessingml" in ctype:
        from docx import Document
        import io
        doc = Document(io.BytesIO(data))
        paras = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            paras.extend(" | ".join(c.text for c in row.cells) for row in table.rows)
        return "\n".join(paras), DocumentFormat.DOCX, {}
    if suffix == ".pptx" or "presentationml" in ctype:
        from pptx import Presentation
        import io
        prs = Presentation(io.BytesIO(data))
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False): texts.append(shape.text)
        return "\n".join(texts), DocumentFormat.PPTX, {"slides": len(prs.slides)}
    if suffix in {".html", ".htm"} or "html" in ctype:
        soup = BeautifulSoup(data, "lxml")
        for node in soup(["script", "style", "nav", "footer"]): node.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        return soup.get_text(" ", strip=True), DocumentFormat.HTML, {"html_title": title}
    try:
        return data.decode("utf-8"), DocumentFormat.TEXT, {}
    except UnicodeDecodeError:
        return "", DocumentFormat.UNKNOWN, {"warning": "Unsupported or non-text document format"}
