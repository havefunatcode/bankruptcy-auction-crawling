"""
PDFDocument를 PostgreSQL에 영속화하는 저장소.

database_manager.DatabaseManager의 저수준 CRUD를 사용해
PDFDocument 단위 트랜잭션을 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from .models import ImageElement, PDFDocument, TableElement, TextElement


class _SupportsInsert(Protocol):
    def insert_pdf_document(
        self,
        notice_id: str,
        file_path: str,
        file_name: str,
        file_size: int,
        page_count: int,
    ) -> Optional[int]: ...

    def insert_text_content(
        self,
        document_id: int,
        page_number: int,
        text_content: str,
        bbox: tuple,
        font_size: Optional[float] = None,
        font_name: Optional[str] = None,
    ) -> bool: ...

    def insert_table_data(
        self,
        document_id: int,
        page_number: int,
        table_index: int,
        table_data: list,
        bbox: tuple,
    ) -> bool: ...

    def insert_image_data(
        self,
        document_id: int,
        page_number: int,
        image_index: int,
        image_path: str,
        width: int,
        height: int,
        format_type: str,
        file_size: int,
        bbox: tuple,
    ) -> bool: ...


@dataclass
class StoreResult:
    document_id: Optional[int]
    text_inserted: int
    tables_inserted: int
    images_inserted: int


class PDFDocumentRepository:
    """PDFDocument → DB 영속화."""

    def __init__(self, db_manager: _SupportsInsert) -> None:
        self.db = db_manager

    def store(self, document: PDFDocument) -> StoreResult:
        notice_id = document.metadata.get("notice_id")
        source_path = document.metadata.get("source_path") or document.file_name
        if not notice_id:
            raise ValueError("document.metadata['notice_id']가 필요합니다")

        try:
            file_size = Path(source_path).stat().st_size if Path(source_path).exists() else 0
        except OSError:
            file_size = 0

        document_id = self.db.insert_pdf_document(
            notice_id=notice_id,
            file_path=str(source_path),
            file_name=document.file_name,
            file_size=file_size,
            page_count=document.page_count,
        )
        if document_id is None:
            return StoreResult(None, 0, 0, 0)

        text_inserted = sum(
            1 for elem in document.text_elements if self._insert_text(document_id, elem)
        )
        tables_inserted = sum(
            1 for table in document.tables if self._insert_table(document_id, table)
        )
        images_inserted = sum(
            1 for img in document.images if self._insert_image(document_id, img)
        )

        return StoreResult(
            document_id=document_id,
            text_inserted=text_inserted,
            tables_inserted=tables_inserted,
            images_inserted=images_inserted,
        )

    def _insert_text(self, document_id: int, elem: TextElement) -> bool:
        return self.db.insert_text_content(
            document_id=document_id,
            page_number=elem.page_number,
            text_content=elem.text,
            bbox=elem.bbox,
            font_size=elem.font_size,
            font_name=elem.font,
        )

    def _insert_table(self, document_id: int, table: TableElement) -> bool:
        return self.db.insert_table_data(
            document_id=document_id,
            page_number=table.page_number,
            table_index=table.table_index,
            table_data=table.data,
            bbox=table.bbox,
        )

    def _insert_image(self, document_id: int, image: ImageElement) -> bool:
        path = image.image_path or ""
        size = 0
        if path:
            try:
                size = Path(path).stat().st_size
            except OSError:
                size = 0
        return self.db.insert_image_data(
            document_id=document_id,
            page_number=image.page_number,
            image_index=image.image_index,
            image_path=path,
            width=0,
            height=0,
            format_type="",
            file_size=size,
            bbox=image.bbox,
        )
