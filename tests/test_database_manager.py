"""DatabaseManager 단위·통합 테스트 (MySQL 8.0+)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from database.database_manager import DatabaseManager


def _mock_conn_with_cursor(cursor: MagicMock) -> MagicMock:
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__.return_value = cursor
    cursor_ctx.__exit__.return_value = False
    conn.cursor.return_value = cursor_ctx
    return conn


@pytest.fixture
def manager() -> DatabaseManager:
    return DatabaseManager()


class TestSchemaSplit:
    def test_split_drops_empty(self, manager: DatabaseManager):
        result = manager._split_sql_statements("\n\n  \n")
        assert result == []

    def test_split_keeps_multiple_statements(self, manager: DatabaseManager):
        sql = """
        CREATE TABLE t1 (id INT);

        CREATE TABLE t2 (id INT);
        """
        result = manager._split_sql_statements(sql)
        assert len(result) == 2
        assert all("CREATE TABLE" in s for s in result)

    def test_single_statement_without_trailing_newline(self, manager: DatabaseManager):
        """줄바꿈 없는 단일 문장은 그대로 1개로 반환."""
        result = manager._split_sql_statements("CREATE TABLE t (id INT);")
        assert len(result) == 1
        assert "CREATE TABLE t" in result[0]


class TestInsertPDFDocument:
    def test_uses_on_duplicate_key_update(self, manager: DatabaseManager):
        cursor = MagicMock(lastrowid=99)
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            doc_id = manager.insert_pdf_document(
                notice_id="500", file_path="/tmp/x.pdf", file_name="x.pdf",
                file_size=1024, page_count=3,
            )
        assert doc_id == 99
        sql = cursor.execute.call_args[0][0]
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "LAST_INSERT_ID(id)" in sql

    def test_returns_none_on_error(self, manager: DatabaseManager):
        with patch("database.database_manager.pymysql.connect", side_effect=Exception("nope")):
            doc_id = manager.insert_pdf_document(
                notice_id="1", file_path="/x", file_name="x", file_size=1, page_count=1,
            )
        assert doc_id is None


class TestInsertChildren:
    def test_text_content_uses_bbox_fields(self, manager: DatabaseManager):
        cursor = MagicMock()
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            ok = manager.insert_text_content(
                document_id=1, page_number=2, text_content="안녕",
                bbox=(1.0, 2.0, 3.0, 4.0), font_size=10.0, font_name="K",
            )
        assert ok is True
        sql = cursor.execute.call_args[0][0]
        args = cursor.execute.call_args[0][1]
        assert "INSERT INTO pdf_text_content" in sql
        assert args == (1, 2, "안녕", 1.0, 2.0, 3.0, 4.0, 10.0, "K")

    def test_table_data_serialized_as_json(self, manager: DatabaseManager):
        import json as _json
        cursor = MagicMock()
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            ok = manager.insert_table_data(
                document_id=1, page_number=1, table_index=0,
                table_data=[["a", "b"], ["c", "d"]],
                bbox=(0, 0, 1, 1),
            )
        assert ok is True
        args = cursor.execute.call_args[0][1]
        payload = _json.loads(args[3])
        assert payload == {"rows": [["a", "b"], ["c", "d"]], "row_count": 2, "col_count": 2}

    def test_image_insert_fields(self, manager: DatabaseManager):
        cursor = MagicMock()
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            ok = manager.insert_image_data(
                document_id=1, page_number=1, image_index=0,
                image_path="/tmp/i.png", width=10, height=20, format_type="png",
                file_size=100, bbox=(0, 0, 1, 1),
            )
        assert ok is True
        args = cursor.execute.call_args[0][1]
        assert args[3] == "/tmp/i.png"
        assert args[6] == "png"


class TestQueries:
    def test_search_uses_ngram_fts(self, manager: DatabaseManager):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            manager.search_text_content("매각", limit=5)
        sql = cursor.execute.call_args[0][0]
        assert "MATCH(ptc.text_content) AGAINST" in sql
        assert "NATURAL LANGUAGE MODE" in sql

    def test_delete_returns_true_when_rowcount_positive(self, manager: DatabaseManager):
        cursor = MagicMock(rowcount=1)
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            assert manager.delete_document_data(1) is True

    def test_delete_returns_false_when_no_rows(self, manager: DatabaseManager):
        cursor = MagicMock(rowcount=0)
        conn = _mock_conn_with_cursor(cursor)
        with patch("database.database_manager.pymysql.connect", return_value=conn):
            assert manager.delete_document_data(1) is False


class TestSchemaFileValid:
    """schema.sql이 MySQL 키워드를 포함하는지(드라이런)."""

    def test_schema_uses_mysql_features(self):
        from database.config_db import SCHEMA_FILE
        with open(SCHEMA_FILE, encoding="utf-8") as f:
            sql = f.read()
        assert "AUTO_INCREMENT" in sql
        assert "ENGINE=InnoDB" in sql
        assert "utf8mb4" in sql
        assert "WITH PARSER ngram" in sql
        assert "ON UPDATE CURRENT_TIMESTAMP" in sql
        # PostgreSQL 잔재가 없어야 함
        assert "SERIAL" not in sql
        assert "JSONB" not in sql
        assert "to_tsvector" not in sql
        assert "pg_size_pretty" not in sql


@pytest.mark.integration
class TestMySQLIntegration:
    """실제 MySQL 인스턴스가 있을 때만 동작."""

    @pytest.fixture
    def live_manager(self):
        mgr = DatabaseManager()
        if not mgr.test_connection():
            pytest.skip("로컬에서 동작하는 MySQL 서버가 없음")
        return mgr

    def test_initialize_and_insert_roundtrip(self, live_manager: DatabaseManager):
        assert live_manager.initialize_database()
        doc_id = live_manager.insert_pdf_document(
            notice_id="__test__",
            file_path="/tmp/test.pdf",
            file_name="test.pdf",
            file_size=1024,
            page_count=2,
        )
        assert doc_id is not None
        assert live_manager.insert_text_content(
            document_id=doc_id, page_number=1, text_content="통합테스트",
            bbox=(0, 0, 1, 1), font_size=10.0, font_name="K",
        )
        # 정리
        assert live_manager.delete_document_data(doc_id)
