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
                    WHERE to_tsvector('simple', ptc.text_content) @@ plainto_tsquery('simple', %s)
                    ORDER BY pd.processed_at DESC
                    LIMIT %s;
                    """
                    
                    cur.execute(sql, (search_term, limit))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to search text content: {e}")
            return []
    
    def update_structured_content(self, document_id: int, structured_data: Dict[str, Any],
                                 status: str = 'completed', error_message: str = None) -> bool:
        """Update structured content for a document"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    UPDATE pdf_documents 
                    SET structured_content = %s,
                        extraction_status = %s,
                        extraction_error = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """
                    
                    cur.execute(sql, (
                        json.dumps(structured_data, ensure_ascii=False) if structured_data else None,
                        status,
                        error_message,
                        document_id
                    ))
                    
                    affected_rows = cur.rowcount
                    conn.commit()
                    
                    if affected_rows > 0:
                        self.logger.info(f"Updated structured content for document ID {document_id}")
                        return True
                    else:
                        self.logger.warning(f"No document found with ID {document_id}")
                        return False
                    
        except Exception as e:
            self.logger.error(f"Failed to update structured content for document {document_id}: {e}")
            return False

    def get_documents_for_structuring(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get documents that need structured content extraction"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT pd.id, pd.notice_id, pd.file_name, pd.file_path,
                           pd.extraction_status, pd.structured_content
                    FROM pdf_documents pd
                    WHERE pd.extraction_status IN ('pending', 'failed')
                       OR pd.structured_content IS NULL
                    ORDER BY pd.processed_at DESC
                    LIMIT %s;
                    """
                    
                    cur.execute(sql, (limit,))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get documents for structuring: {e}")
            return []

    def get_structured_content_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get structured content summary using the view"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM pdf_structured_analysis LIMIT %s;"
                    cur.execute(sql, (limit,))
                    
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get structured content summary: {e}")
            return []

    def search_structured_content(self, search_term: str, section: str = None, 
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """Search in structured content"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    if section:
                        # Search in specific section
                        sql = """
                        SELECT pd.notice_id, pd.file_name, 
                               pd.structured_content->'sections'->%s as section_data
                        FROM pdf_documents pd
                        WHERE pd.structured_content->'sections'->%s::text ILIKE %s
                        ORDER BY pd.processed_at DESC
                        LIMIT %s;
                        """
                        cur.execute(sql, (section, section, f'%{search_term}%', limit))
                    else:
                        # Search in all structured content
                        sql = """
                        SELECT pd.notice_id, pd.file_name, pd.structured_content
                        FROM pdf_documents pd
                        WHERE pd.structured_content::text ILIKE %s
                        ORDER BY pd.processed_at DESC
                        LIMIT %s;
                        """
                        cur.execute(sql, (f'%{search_term}%', limit))
                    
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to search structured content: {e}")
            return []

    def get_assets_by_type(self, asset_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all assets of a specific type"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT pd.notice_id, pd.file_name,
                           pd.structured_content->'sections'->'매각대상자산'->>'asset_type' as asset_type,
                           jsonb_array_elements(
                               COALESCE(pd.structured_content->'sections'->'매각대상자산'->'assets', '[]'::jsonb)
                           ) as asset
                    FROM pdf_documents pd
                    WHERE pd.structured_content->'sections'->'매각대상자산'->>'asset_type' ILIKE %s
                    ORDER BY pd.processed_at DESC
                    LIMIT %s;
                    """
                    
                    cur.execute(sql, (f'%{asset_type}%', limit))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get assets by type: {e}")
            return []

    # Dynamic Section Processing Methods
    
    def store_dynamic_sections(self, document_id: int, processing_result) -> bool:
        """Store dynamic section processing result"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Update document with dynamic sections JSON and metadata
                    sql_update = """
                    UPDATE pdf_documents 
                    SET dynamic_sections = %s,
                        document_metadata = %s,
                        section_extraction_status = %s,
                        section_extraction_error = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """
                    
                    # Convert processing result to JSON-serializable format
                    from pdf_processing.dynamic_section_processor import DynamicSectionProcessor
                    processor = DynamicSectionProcessor()
                    json_result = processor.to_json_serializable(processing_result)
                    
                    cur.execute(sql_update, (
                        json.dumps(json_result, ensure_ascii=False),
                        json.dumps(processing_result.document_metadata, ensure_ascii=False),
                        'completed' if processing_result.success else 'failed',
                        processing_result.error_message,
                        document_id
                    ))
                    
                    if not processing_result.success:
                        conn.commit()
                        return True
                    
                    # Store individual sections
                    for section_key, section_content in processing_result.sections.items():
                        section_id = self._insert_section(cur, document_id, section_key, section_content)
                        
                        if section_id:
                            # Store subsections
                            for subsection_key, subsection_content in section_content.subsections.items():
                                self._insert_subsection(cur, section_id, subsection_key, subsection_content)
                            
                            # Create section-table relationships
                            for table in section_content.tables:
                                self._link_section_table(cur, section_id, table)
                            
                            # Create section-image relationships
                            for image in section_content.images:
                                self._link_section_image(cur, section_id, image)
                    
                    # Store processing result record
                    self._insert_processing_result(cur, document_id, 'dynamic_sections', processing_result)
                    
                    conn.commit()
                    self.logger.info(f"Stored dynamic sections for document ID {document_id}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to store dynamic sections for document {document_id}: {e}")
            return False
    
    def _insert_section(self, cursor, document_id: int, section_key: str, section_content) -> Optional[int]:
        """Insert a section record and return section ID"""
        try:
            sql = """
            INSERT INTO pdf_sections 
            (document_id, section_key, section_name, section_type, section_number, 
             original_title, text_content, start_line, content_length, line_count, section_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id, section_key) 
            DO UPDATE SET 
                section_name = EXCLUDED.section_name,
                section_type = EXCLUDED.section_type,
                text_content = EXCLUDED.text_content,
                section_metadata = EXCLUDED.section_metadata
            RETURNING id;
            """
            
            cursor.execute(sql, (
                document_id,
                section_key,
                section_content.section_name,
                section_content.metadata.get('section_type'),
                section_content.metadata.get('section_number'),
                section_content.metadata.get('original_title'),
                section_content.text_content,
                section_content.metadata.get('start_line'),
                section_content.metadata.get('content_length'),
                section_content.metadata.get('line_count'),
                json.dumps(section_content.metadata, ensure_ascii=False)
            ))
            
            result = cursor.fetchone()
            return result[0] if result else None
            
        except Exception as e:
            self.logger.error(f"Failed to insert section {section_key}: {e}")
            return None
    
    def _insert_subsection(self, cursor, section_id: int, subsection_key: str, subsection_content) -> bool:
        """Insert a subsection record"""
        try:
            sql = """
            INSERT INTO pdf_subsections 
            (section_id, subsection_key, subsection_name, text_content, subsection_metadata)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (section_id, subsection_key) 
            DO UPDATE SET 
                subsection_name = EXCLUDED.subsection_name,
                text_content = EXCLUDED.text_content,
                subsection_metadata = EXCLUDED.subsection_metadata;
            """
            
            cursor.execute(sql, (
                section_id,
                subsection_key,
                subsection_content.section_name,
                subsection_content.text_content,
                json.dumps(subsection_content.metadata, ensure_ascii=False)
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to insert subsection {subsection_key}: {e}")
            return False
    
    def _link_section_table(self, cursor, section_id: int, table: Dict[str, Any]) -> bool:
        """Link a table to a section"""
        try:
            # Find table ID based on table metadata
            table_page = table.get('page_number')
            if table_page is None:
                return False
                
            # Get table ID from pdf_tables
            sql_find = """
            SELECT id FROM pdf_tables 
            WHERE document_id = (
                SELECT document_id FROM pdf_sections WHERE id = %s
            ) AND page_number = %s
            LIMIT 1;
            """
            
            cursor.execute(sql_find, (section_id, table_page))
            table_record = cursor.fetchone()
            
            if not table_record:
                return False
                
            table_id = table_record[0]
            
            # Insert relationship
            sql_insert = """
            INSERT INTO pdf_section_tables 
            (section_id, table_id, assignment_confidence, assignment_reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (section_id, table_id) DO NOTHING;
            """
            
            cursor.execute(sql_insert, (
                section_id,
                table_id,
                1.0,  # Default confidence
                'automatic_assignment'
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to link table to section {section_id}: {e}")
            return False
    
    def _link_section_image(self, cursor, section_id: int, image: Dict[str, Any]) -> bool:
        """Link an image to a section"""
        try:
            # Find image ID based on image metadata
            image_page = image.get('page_number')
            if image_page is None:
                return False
                
            # Get image ID from pdf_images
            sql_find = """
            SELECT id FROM pdf_images 
            WHERE document_id = (
                SELECT document_id FROM pdf_sections WHERE id = %s
            ) AND page_number = %s
            LIMIT 1;
            """
            
            cursor.execute(sql_find, (section_id, image_page))
            image_record = cursor.fetchone()
            
            if not image_record:
                return False
                
            image_id = image_record[0]
            
            # Insert relationship
            sql_insert = """
            INSERT INTO pdf_section_images 
            (section_id, image_id, assignment_confidence, assignment_reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (section_id, image_id) DO NOTHING;
            """
            
            cursor.execute(sql_insert, (
                section_id,
                image_id,
                1.0,  # Default confidence
                'automatic_assignment'
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to link image to section {section_id}: {e}")
            return False
    
    def _insert_processing_result(self, cursor, document_id: int, method: str, result) -> bool:
        """Insert processing result record"""
        try:
            sql = """
            INSERT INTO pdf_processing_results 
            (document_id, processing_method, success, confidence_score, 
             processing_notes, error_message, result_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id, processing_method) 
            DO UPDATE SET 
                success = EXCLUDED.success,
                confidence_score = EXCLUDED.confidence_score,
                processing_notes = EXCLUDED.processing_notes,
                error_message = EXCLUDED.error_message,
                result_data = EXCLUDED.result_data,
                created_at = CURRENT_TIMESTAMP;
            """
            
            # Convert processing result to JSON
            from pdf_processing.dynamic_section_processor import DynamicSectionProcessor
            processor = DynamicSectionProcessor()
            json_result = processor.to_json_serializable(result)
            
            cursor.execute(sql, (
                document_id,
                method,
                result.success,
                result.confidence_score,
                result.processing_notes,
                result.error_message,
                json.dumps(json_result, ensure_ascii=False)
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to insert processing result: {e}")
            return False
    
    def get_documents_for_dynamic_processing(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get documents that need dynamic section processing"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT pd.id, pd.notice_id, pd.file_name, pd.file_path,
                           pd.section_extraction_status, pd.dynamic_sections
                    FROM pdf_documents pd
                    WHERE pd.section_extraction_status IN ('pending', 'failed')
                       OR pd.dynamic_sections IS NULL
                    ORDER BY pd.processed_at DESC
                    LIMIT %s;
                    """
                    
                    cur.execute(sql, (limit,))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get documents for dynamic processing: {e}")
            return []
    
    def get_section_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get section processing summary"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM pdf_section_analysis LIMIT %s;"
                    cur.execute(sql, (limit,))
                    
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get section summary: {e}")
            return []
    
    def search_sections(self, search_term: str, section_type: str = None, 
                       limit: int = 50) -> List[Dict[str, Any]]:
        """Search sections by content or type"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    if section_type:
                        sql = """
                        SELECT pd.notice_id, pd.file_name, ps.section_name, 
                               ps.section_type, ps.text_content,
                               ts_rank(to_tsvector(ps.text_content), 
                                      plainto_tsquery(%s)) as relevance
                        FROM pdf_documents pd
                        JOIN pdf_sections ps ON pd.id = ps.document_id
                        WHERE ps.section_type = %s 
                          AND ps.text_content ILIKE %s
                        ORDER BY relevance DESC
                        LIMIT %s;
                        """
                        cur.execute(sql, (search_term, section_type, f'%{search_term}%', limit))
                    else:
                        sql = """
                        SELECT pd.notice_id, pd.file_name, ps.section_name, 
                               ps.section_type, ps.text_content,
                               1.0 as relevance
                        FROM pdf_documents pd
                        JOIN pdf_sections ps ON pd.id = ps.document_id
                        WHERE ps.text_content ILIKE %s
                        ORDER BY pd.notice_id, ps.section_key
                        LIMIT %s;
                        """
                        cur.execute(sql, (f'%{search_term}%', limit))
                    
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to search sections: {e}")
            return []
    
    def get_sections_by_document(self, notice_id: str, file_name: str) -> List[Dict[str, Any]]:
        """Get all sections for a specific document"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT ps.section_key, ps.section_name, ps.section_type,
                           ps.text_content, ps.section_metadata,
                           COUNT(pst.table_id) as tables_count,
                           COUNT(psi.image_id) as images_count,
                           COUNT(pss.id) as subsections_count
                    FROM pdf_documents pd
                    JOIN pdf_sections ps ON pd.id = ps.document_id
                    LEFT JOIN pdf_section_tables pst ON ps.id = pst.section_id
                    LEFT JOIN pdf_section_images psi ON ps.id = psi.section_id
                    LEFT JOIN pdf_subsections pss ON ps.id = pss.section_id
                    WHERE pd.notice_id = %s AND pd.file_name = %s
                    GROUP BY ps.id, ps.section_key, ps.section_name, ps.section_type,
                             ps.text_content, ps.section_metadata
                    ORDER BY ps.section_key;
                    """
                    
                    cur.execute(sql, (notice_id, file_name))
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            self.logger.error(f"Failed to get sections for document: {e}")
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