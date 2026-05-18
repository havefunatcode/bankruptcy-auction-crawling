"""PDFDocumentRepository 단위 테스트 (DB는 모킹)."""
from __future__ import annotations

import pytest

from pdf_processing.models import ImageElement, PDFDocument, TableElement, TextElement
from pdf_processing.persistence import PDFDocumentRepository


class _StubDB:
    def __init__(self, doc_id: int | None = 42):
        self.doc_id = doc_id
        self.texts: list[dict] = []
        self.tables: list[dict] = []
        self.images: list[dict] = []
        self.doc_calls: list[dict] = []

    def insert_pdf_document(self, **kwargs):
        self.doc_calls.append(kwargs)
        return self.doc_id

    def insert_text_content(self, **kwargs):
        self.texts.append(kwargs)
        return True

    def insert_table_data(self, **kwargs):
        self.tables.append(kwargs)
        return True

    def insert_image_data(self, **kwargs):
        self.images.append(kwargs)
        return True


def _doc_with_notice(notice_id: str = "500") -> PDFDocument:
    doc = PDFDocument(
        file_name="x.pdf", page_count=3,
        metadata={"notice_id": notice_id, "source_path": "/tmp/missing.pdf"},
    )
    doc.text_elements.append(
        TextElement(text="안녕", bbox=(0, 0, 1, 1), page_number=1,
                    element_type="paragraph", font_size=10.0, font="K")
    )
    doc.text_elements.append(
        TextElement(text="제목", bbox=(0, 0, 2, 2), page_number=1,
                    element_type="heading", heading_level=1)
    )
    doc.tables.append(
        TableElement(data=[["a", "b"]], bbox=(0, 0, 5, 5),
                     row_count=1, col_count=2, page_number=2, table_index=0)
    )
    doc.images.append(
        ImageElement(bbox=(0, 0, 3, 3), page_number=3, image_index=0,
                     image_path="/tmp/img.png")
    )
    return doc


class TestStore:
    def test_inserts_document_then_children(self):
        db = _StubDB()
        repo = PDFDocumentRepository(db)
        result = repo.store(_doc_with_notice())

        assert result.document_id == 42
        assert result.text_inserted == 2
        assert result.tables_inserted == 1
        assert result.images_inserted == 1

    def test_passes_notice_id_to_db(self):
        db = _StubDB()
        repo = PDFDocumentRepository(db)
        repo.store(_doc_with_notice("777"))
        assert db.doc_calls[0]["notice_id"] == "777"
        assert db.doc_calls[0]["page_count"] == 3
        assert db.doc_calls[0]["file_name"] == "x.pdf"

    def test_requires_notice_id(self):
        doc = PDFDocument(file_name="x.pdf", page_count=1)  # metadata 비어있음
        repo = PDFDocumentRepository(_StubDB())
        with pytest.raises(ValueError):
            repo.store(doc)

    def test_handles_doc_insert_failure(self):
        db = _StubDB(doc_id=None)
        repo = PDFDocumentRepository(db)
        result = repo.store(_doc_with_notice())
        assert result.document_id is None
        assert result.text_inserted == 0
        assert result.tables_inserted == 0
        assert db.texts == []
        assert db.tables == []

    def test_text_payload_shape(self):
        db = _StubDB()
        repo = PDFDocumentRepository(db)
        repo.store(_doc_with_notice())
        first_text = db.texts[0]
        assert first_text["text_content"] == "안녕"
        assert first_text["page_number"] == 1
        assert first_text["bbox"] == (0, 0, 1, 1)
        assert first_text["font_size"] == 10.0

    def test_table_payload_shape(self):
        db = _StubDB()
        repo = PDFDocumentRepository(db)
        repo.store(_doc_with_notice())
        first_table = db.tables[0]
        assert first_table["table_data"] == [["a", "b"]]
        assert first_table["table_index"] == 0
        assert first_table["page_number"] == 2

    def test_skips_image_size_for_missing_path(self):
        doc = PDFDocument(
            file_name="x.pdf", page_count=1,
            metadata={"notice_id": "1", "source_path": "/tmp/x.pdf"},
        )
        doc.images.append(
            ImageElement(bbox=(0, 0, 1, 1), page_number=1, image_index=0,
                         image_path=None)
        )
        db = _StubDB()
        repo = PDFDocumentRepository(db)
        result = repo.store(doc)
        assert result.images_inserted == 1
        assert db.images[0]["image_path"] == ""
        assert db.images[0]["file_size"] == 0
