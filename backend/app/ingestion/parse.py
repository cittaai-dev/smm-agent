from pathlib import Path


def extract_text(file_path: str) -> str:
    """L1-only extraction for Step 1: pdf / docx / plain text. No OCR, no tables."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    return Path(file_path).read_text(encoding="utf-8", errors="ignore")


def _extract_pdf(file_path: str) -> str:
    import pymupdf

    with pymupdf.open(file_path) as doc:
        return "\n\n".join(page.get_text() for page in doc)


def _extract_docx(file_path: str) -> str:
    import docx

    document = docx.Document(file_path)
    return "\n\n".join(p.text for p in document.paragraphs)


def split_paragraphs(text: str) -> list[str]:
    """Structural (L1) split: one chunk per non-empty paragraph, in document order."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]
