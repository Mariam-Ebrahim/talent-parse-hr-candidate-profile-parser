from pypdf import PdfReader

from .errors import ParseError


def extract_text_from_pdf(file) -> str:
    """Return the text of a PDF (path or file-like object)."""
    try:
        reader = PdfReader(file)
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:  # corrupted / encrypted files raise several error types
        raise ParseError("This PDF could not be read. Try another file or paste the text.") from exc
    if not text:
        raise ParseError("No text found in this PDF. It may be a scanned image: paste the text instead.")
    return text
