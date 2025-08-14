"""
Database manager for PostgreSQL operations
"""
import os
import json
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
from utils.logger import setup_logger
from .config_db import DATABASE_CONFIG, SCHEMA_FILE


class DatabaseManager:
    """PostgreSQL database manager for PDF processing"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.connection_params = DATABASE_CONFIG
        
    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
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
    
    def initialize_database(self) -> bool:
        """Initialize database with schema"""
        try:
            # First, try to create the database if it doesn't exist
            self._create_database_if_not_exists()
            
            # Then create tables
            with self.get_connection() as conn:
                with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
                    conn.commit()
                
                self.logger.info("Database schema initialized successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False
    
    def _create_database_if_not_exists(self):
        """Create database if it doesn't exist"""
        try:
            # Connect to default postgres database
            default_params = self.connection_params.copy()
            default_params['database'] = 'postgres'
            
            with psycopg2.connect(**default_params) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Check if database exists
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (self.connection_params['database'],)
                    )
                    
                    if not cur.fetchone():
                        # Create database
                        cur.execute(
                            f"CREATE DATABASE {self.connection_params['database']}"
                        )
                        self.logger.info(f"Created database: {self.connection_params['database']}")
                    else:
                        self.logger.info(f"Database already exists: {self.connection_params['database']}")
                        
        except Exception as e:
            self.logger.warning(f"Could not create database: {e}")
    
    def insert_pdf_document(self, notice_id: str, file_path: str, file_name: str, 
                           file_size: int, page_count: int) -> Optional[int]:
        """Insert PDF document metadata"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    INSERT INTO pdf_documents 
                    (notice_id, file_path, file_name, file_size, page_count, processed_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (notice_id, file_name) 
                    DO UPDATE SET 
                        file_path = EXCLUDED.file_path,
                        file_size = EXCLUDED.file_size,
                        page_count = EXCLUDED.page_count,
                        processed_at = EXCLUDED.processed_at,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id;
                    """
                    
                    cur.execute(sql, (
                        notice_id, file_path, file_name, 
                        file_size, page_count, datetime.now()
                    ))
                    
                    document_id = cur.fetchone()[0]
                    conn.commit()
                    
                    self.logger.info(f"Inserted PDF document: {file_name} (ID: {document_id})")
                    return document_id
                    
        except Exception as e:
            self.logger.error(f"Failed to insert PDF document: {e}")
            return None
    
    def insert_text_content(self, document_id: int, page_number: int, 
                           text_content: str, bbox: Tuple[float, float, float, float],
                           font_size: Optional[float] = None, 
                           font_name: Optional[str] = None) -> bool:
        """Insert extracted text content"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    INSERT INTO pdf_text_content 
                    (document_id, page_number, text_content, bbox_x0, bbox_y0, bbox_x1, bbox_y1, font_size, font_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    
                    cur.execute(sql, (
                        document_id, page_number, text_content,
                        bbox[0], bbox[1], bbox[2], bbox[3],
                        font_size, font_name
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to insert text content: {e}")
            return False
    
    def insert_table_data(self, document_id: int, page_number: int, table_index: int,
                         table_data: List[List[str]], bbox: Tuple[float, float, float, float]) -> bool:
        """Insert extracted table data"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Convert table data to JSON
                    table_json = {
                        'rows': table_data,
                        'row_count': len(table_data),
                        'col_count': len(table_data[0]) if table_data else 0
                    }
                    
                    sql = """
                    INSERT INTO pdf_tables 
                    (document_id, page_number, table_index, table_data, row_count, col_count, 
                     bbox_x0, bbox_y0, bbox_x1, bbox_y1)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    
                    cur.execute(sql, (
                        document_id, page_number, table_index,
                        json.dumps(table_json, ensure_ascii=False),
                        len(table_data), len(table_data[0]) if table_data else 0,
                        bbox[0], bbox[1], bbox[2], bbox[3]
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to insert table data: {e}")
            return False
    
    def insert_image_data(self, document_id: int, page_number: int, image_index: int,
                         image_path: str, width: int, height: int, format_type: str,
                         file_size: int, bbox: Tuple[float, float, float, float]) -> bool:
        """Insert extracted image data"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    INSERT INTO pdf_images 
                    (document_id, page_number, image_index, image_path, width, height, format, file_size,
                     bbox_x0, bbox_y0, bbox_x1, bbox_y1)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    
                    cur.execute(sql, (
                        document_id, page_number, image_index, image_path,
                        width, height, format_type, file_size,
                        bbox[0], bbox[1], bbox[2], bbox[3]
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to insert image data: {e}")
            return False
    
    def get_document_by_notice_and_name(self, notice_id: str, file_name: str) -> Optional[Dict[str, Any]]:
        """Get document by notice ID and filename"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT * FROM pdf_documents 
                    WHERE notice_id = %s AND file_name = %s;
                    """
                    
                    cur.execute(sql, (notice_id, file_name))
                    result = cur.fetchone()
                    
                    return dict(result) if result else None
                    
        except Exception as e:
            self.logger.error(f"Failed to get document: {e}")
            return None
    
    def get_processing_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get processing summary using the view"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM pdf_processing_summary LIMIT %s;"
                    cur.execute(sql, (limit,))
                    
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get processing summary: {e}")
            return []
    
    def delete_document_data(self, document_id: int) -> bool:
        """Delete document and all related data (cascading)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = "DELETE FROM pdf_documents WHERE id = %s;"
                    cur.execute(sql, (document_id,))
                    
                    affected_rows = cur.rowcount
                    conn.commit()
                    
                    self.logger.info(f"Deleted document ID {document_id} and related data")
                    return affected_rows > 0
                    
        except Exception as e:
            self.logger.error(f"Failed to delete document data: {e}")
            return False
    
    def search_text_content(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search text content using full-text search"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT pd.notice_id, pd.file_name, ptc.page_number, 
                           ptc.text_content, ptc.bbox_x0, ptc.bbox_y0, ptc.bbox_x1, ptc.bbox_y1
                    FROM pdf_text_content ptc
                    JOIN pdf_documents pd ON ptc.document_id = pd.id
                    WHERE to_tsvector('korean', ptc.text_content) @@ plainto_tsquery('korean', %s)
                    ORDER BY pd.processed_at DESC
                    LIMIT %s;
                    """
                    
                    cur.execute(sql, (search_term, limit))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to search text content: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
                
                self.logger.info("Database connection test successful")
                return True
                
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False