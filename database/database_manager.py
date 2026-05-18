"""
PostgreSQL 데이터 접근 계층.

opendataloader-pdf로 추출된 PDF 컨텐츠를 저장·조회한다.
구조화 섹션 추출/검색 로직은 외부 도메인 계층으로 위임한다.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from utils.logger import setup_logger
from .config_db import DATABASE_CONFIG, SCHEMA_FILE


class DatabaseManager:
    """PDF 추출 결과를 저장·조회하는 저수준 데이터 접근 계층."""

    def __init__(self) -> None:
        self.logger = setup_logger(__name__)
        self.connection_params = DATABASE_CONFIG

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.Error as e:
            self.logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            return True
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False

    def initialize_database(self) -> bool:
        try:
            self._create_database_if_not_exists()
            with self.get_connection() as conn:
                with open(SCHEMA_FILE, encoding="utf-8") as f:
                    schema_sql = f.read()
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
                    conn.commit()
            self.logger.info("Database schema initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False

    def _create_database_if_not_exists(self) -> None:
        try:
            default_params = self.connection_params.copy()
            default_params["database"] = "postgres"
            with psycopg2.connect(**default_params) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (self.connection_params["database"],),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            f"CREATE DATABASE {self.connection_params['database']}"
                        )
                        self.logger.info(
                            f"Created database: {self.connection_params['database']}"
                        )
        except Exception as e:
            self.logger.warning(f"Could not ensure database exists: {e}")

    def insert_pdf_document(
        self,
        notice_id: str,
        file_path: str,
        file_name: str,
        file_size: int,
        page_count: int,
    ) -> Optional[int]:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pdf_documents
                            (notice_id, file_path, file_name, file_size, page_count, processed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (notice_id, file_name) DO UPDATE SET
                            file_path = EXCLUDED.file_path,
                            file_size = EXCLUDED.file_size,
                            page_count = EXCLUDED.page_count,
                            processed_at = EXCLUDED.processed_at,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id;
                        """,
                        (notice_id, file_path, file_name, file_size, page_count, datetime.now()),
                    )
                    document_id = cur.fetchone()[0]
                    conn.commit()
                    return document_id
        except Exception as e:
            self.logger.error(f"Failed to insert PDF document: {e}")
            return None

    def insert_text_content(
        self,
        document_id: int,
        page_number: int,
        text_content: str,
        bbox: Tuple[float, float, float, float],
        font_size: Optional[float] = None,
        font_name: Optional[str] = None,
    ) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pdf_text_content
                            (document_id, page_number, text_content,
                             bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                             font_size, font_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            document_id, page_number, text_content,
                            bbox[0], bbox[1], bbox[2], bbox[3],
                            font_size, font_name,
                        ),
                    )
                    conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to insert text content: {e}")
            return False

    def insert_table_data(
        self,
        document_id: int,
        page_number: int,
        table_index: int,
        table_data: List[List[str]],
        bbox: Tuple[float, float, float, float],
    ) -> bool:
        try:
            payload = {
                "rows": table_data,
                "row_count": len(table_data),
                "col_count": len(table_data[0]) if table_data else 0,
            }
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pdf_tables
                            (document_id, page_number, table_index,
                             table_data, row_count, col_count,
                             bbox_x0, bbox_y0, bbox_x1, bbox_y1)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            document_id, page_number, table_index,
                            json.dumps(payload, ensure_ascii=False),
                            payload["row_count"], payload["col_count"],
                            bbox[0], bbox[1], bbox[2], bbox[3],
                        ),
                    )
                    conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to insert table data: {e}")
            return False

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
        bbox: Tuple[float, float, float, float],
    ) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pdf_images
                            (document_id, page_number, image_index, image_path,
                             width, height, format, file_size,
                             bbox_x0, bbox_y0, bbox_x1, bbox_y1)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            document_id, page_number, image_index, image_path,
                            width, height, format_type, file_size,
                            bbox[0], bbox[1], bbox[2], bbox[3],
                        ),
                    )
                    conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to insert image data: {e}")
            return False

    def get_document_by_notice_and_name(
        self, notice_id: str, file_name: str
    ) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT * FROM pdf_documents
                        WHERE notice_id = %s AND file_name = %s;
                        """,
                        (notice_id, file_name),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get document: {e}")
            return None

    def get_processing_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute("SELECT * FROM pdf_processing_summary LIMIT %s;", (limit,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get processing summary: {e}")
            return []

    def search_text_content(
        self, search_term: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT pd.notice_id, pd.file_name, ptc.page_number,
                               ptc.text_content, ptc.bbox_x0, ptc.bbox_y0,
                               ptc.bbox_x1, ptc.bbox_y1
                        FROM pdf_text_content ptc
                        JOIN pdf_documents pd ON ptc.document_id = pd.id
                        WHERE to_tsvector('simple', ptc.text_content)
                              @@ plainto_tsquery('simple', %s)
                        ORDER BY pd.processed_at DESC
                        LIMIT %s;
                        """,
                        (search_term, limit),
                    )
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to search text content: {e}")
            return []

    def delete_document_data(self, document_id: int) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM pdf_documents WHERE id = %s;", (document_id,)
                    )
                    affected = cur.rowcount
                    conn.commit()
            return affected > 0
        except Exception as e:
            self.logger.error(f"Failed to delete document data: {e}")
            return False
