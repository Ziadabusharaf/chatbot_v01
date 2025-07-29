from app import process_pdf
import io
import pytest

PyPDF2 = pytest.importorskip("PyPDF2")
from PyPDF2 import PdfWriter

def test_process_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as f:
        writer.write(f)
    assert process_pdf(str(pdf_path)).strip() == ""
