"""OpenDataLoaderAdapter 단위 테스트."""
from pathlib import Path

import pytest

from pdf_processing.models import PDFDocument, TableElement, TextElement
from pdf_processing.opendataloader_adapter import OpenDataLoaderAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter() -> OpenDataLoaderAdapter:
    return OpenDataLoaderAdapter()


@pytest.fixture
def text_document(adapter) -> PDFDocument:
    return adapter.parse_file(FIXTURES / "sample_text_pdf.json")


@pytest.fixture
def scanned_document(adapter) -> PDFDocument:
    return adapter.parse_file(FIXTURES / "sample_scanned_pdf.json")


class TestParseDict:
    def test_returns_pdf_document(self, adapter):
        result = adapter.parse_dict({"file name": "x.pdf", "number of pages": 1, "kids": []})
        assert isinstance(result, PDFDocument)
        assert result.file_name == "x.pdf"
        assert result.page_count == 1

    def test_extracts_paragraph(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf",
            "number of pages": 1,
            "kids": [
                {
                    "type": "paragraph",
                    "page number": 1,
                    "bounding box": [10.0, 20.0, 30.0, 40.0],
                    "font": "Arial",
                    "font size": 12.0,
                    "content": "안녕하세요",
                }
            ],
        })
        assert len(doc.text_elements) == 1
        elem = doc.text_elements[0]
        assert elem.text == "안녕하세요"
        assert elem.element_type == "paragraph"
        assert elem.page_number == 1
        assert elem.bbox == (10.0, 20.0, 30.0, 40.0)
        assert elem.font == "Arial"
        assert elem.font_size == 12.0

    def test_extracts_heading_with_level(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{
                "type": "heading",
                "page number": 1,
                "bounding box": [0, 0, 100, 20],
                "heading level": 2,
                "content": "제2장",
            }],
        })
        h = doc.headings[0]
        assert h.heading_level == 2
        assert h.element_type == "heading"

    def test_skips_empty_content(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{
                "type": "paragraph", "page number": 1,
                "bounding box": [0, 0, 1, 1], "content": "   ",
            }],
        })
        assert doc.text_elements == []

    def test_extracts_table(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{
                "type": "table",
                "page number": 1,
                "bounding box": [0, 0, 100, 100],
                "number of rows": 2,
                "number of columns": 2,
                "rows": [
                    {"type": "table row", "row number": 1, "cells": [
                        {"type": "table cell", "row number": 1, "column number": 1,
                         "kids": [{"type": "paragraph", "content": "헤더1"}]},
                        {"type": "table cell", "row number": 1, "column number": 2,
                         "kids": [{"type": "paragraph", "content": "헤더2"}]},
                    ]},
                    {"type": "table row", "row number": 2, "cells": [
                        {"type": "table cell", "row number": 2, "column number": 1,
                         "kids": [{"type": "paragraph", "content": "값1"}]},
                        {"type": "table cell", "row number": 2, "column number": 2,
                         "kids": [{"type": "paragraph", "content": "값2"}]},
                    ]},
                ],
            }],
        })
        assert len(doc.tables) == 1
        t = doc.tables[0]
        assert t.row_count == 2
        assert t.col_count == 2
        assert t.data == [["헤더1", "헤더2"], ["값1", "값2"]]

    def test_table_text_does_not_leak_to_text_elements(self, adapter):
        """테이블 셀 내부 paragraph는 text_elements가 아니라 table.data로만 들어가야 한다."""
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{
                "type": "table",
                "page number": 1,
                "bounding box": [0, 0, 100, 100],
                "number of rows": 1, "number of columns": 1,
                "rows": [{"type": "table row", "row number": 1, "cells": [
                    {"type": "table cell", "row number": 1, "column number": 1,
                     "kids": [{"type": "paragraph", "content": "셀내용"}]},
                ]}],
            }],
        })
        assert doc.text_elements == []
        assert doc.tables[0].data[0][0] == "셀내용"

    def test_extracts_image(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{
                "type": "image",
                "page number": 3,
                "bounding box": [5, 6, 7, 8],
                "path": "/tmp/img.png",
            }],
        })
        assert len(doc.images) == 1
        img = doc.images[0]
        assert img.page_number == 3
        assert img.image_path == "/tmp/img.png"
        assert img.bbox == (5.0, 6.0, 7.0, 8.0)

    def test_handles_missing_bbox(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "kids": [{"type": "paragraph", "page number": 1, "content": "x"}],
        })
        assert doc.text_elements[0].bbox == (0.0, 0.0, 0.0, 0.0)

    def test_handles_empty_kids(self, adapter):
        doc = adapter.parse_dict({"file name": "t.pdf", "number of pages": 1})
        assert doc.text_elements == []
        assert doc.tables == []
        assert doc.images == []

    def test_metadata_captured(self, adapter):
        doc = adapter.parse_dict({
            "file name": "t.pdf", "number of pages": 1,
            "author": "테스터", "title": "제목",
            "creation date": "2025-01-01", "modification date": "2025-01-02",
            "kids": [],
        })
        assert doc.metadata == {
            "author": "테스터",
            "title": "제목",
            "creation_date": "2025-01-01",
            "modification_date": "2025-01-02",
        }


class TestRealTextPDFFixture:
    """실제 텍스트 PDF 출력으로 검증."""

    def test_page_count(self, text_document):
        assert text_document.page_count == 20

    def test_has_headings(self, text_document):
        assert len(text_document.headings) > 0
        assert any("매각" in h.text or "공고" in h.text for h in text_document.headings)

    def test_has_tables(self, text_document):
        assert len(text_document.tables) > 0
        for t in text_document.tables:
            assert t.row_count > 0
            assert t.col_count > 0
            assert len(t.data) == t.row_count

    def test_table_indexing_sequential(self, text_document):
        for i, t in enumerate(text_document.tables):
            assert t.table_index == i

    def test_full_text_returns_string(self, text_document):
        text = text_document.full_text
        assert isinstance(text, str)
        assert len(text) > 0

    def test_no_table_cell_content_in_text_elements(self, text_document):
        """테이블 셀 안의 단어가 별도 text_element로 중복 추출되지 않아야 함."""
        for table in text_document.tables:
            for row in table.data:
                for cell in row:
                    if cell:
                        same_text = [e for e in text_document.text_elements if e.text == cell]
                        assert len(same_text) == 0, (
                            f"테이블 셀 텍스트 '{cell}'가 text_elements에 중복됨"
                        )


class TestRealScannedPDFFixture:
    """스캔본 PDF(이미지 기반) 검증."""

    def test_mostly_images(self, scanned_document):
        assert len(scanned_document.images) > 0

    def test_can_still_parse_without_text(self, scanned_document):
        assert scanned_document.page_count > 0
        assert isinstance(scanned_document, PDFDocument)
