"""Export rendering compatibility layer delegating to DocumentGenerator."""

from app.services.document_generator import DocumentGenerator


def render_docx(document, version, content: dict) -> bytes:
    return DocumentGenerator.generate_docx(document, version, content)


def render_pdf(document, version, content: dict) -> bytes:
    return DocumentGenerator.generate_pdf(document, version, content)
