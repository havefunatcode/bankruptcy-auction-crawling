"""
Rule-based Database Manager
Handles storage for rule-based PDF processing results
"""
import json
import psycopg2
import psycopg2.extras
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import contextmanager

from .config_db import DATABASE_CONFIG
from pdf_processing.rule_based_pdf_processor import ProcessingResult
from pdf_processing.evidence_system import ExtractedValue
from utils.logger import setup_logger


class RuleBasedDBManager:
    """Database manager for rule-based PDF processing"""
    
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
    
    def initialize_schema(self) -> bool:
        """Initialize the rule-based schema"""
        try:
            schema_file = "database/rule_based_schema.sql"
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(schema_sql)
                    conn.commit()
            
            self.logger.info("Rule-based schema initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize schema: {e}")
            return False
    
    def store_processing_result(self, result: ProcessingResult) -> Optional[int]:
        """
        Store complete processing result
        
        Args:
            result: ProcessingResult from rule-based processor
            
        Returns:
            Document ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Insert main document record
                    doc_id = self._insert_document(cur, result)
                    
                    if doc_id:
                        # Insert sections
                        for section in result.extracted_sections:
                            section_id = self._insert_section(cur, doc_id, section, result)
                            
                            # Insert normalized fields if any
                            if section.section_id in result.normalized_fields:
                                self._update_section_with_fields(
                                    cur, section_id, result.normalized_fields[section.section_id]
                                )
                        
                        # Update document statistics
                        self._update_document_statistics(cur, doc_id, result)
                        
                        conn.commit()
                        self.logger.info(f"Stored processing result for {result.file_name} (doc_id: {doc_id})")
                        return doc_id
                    
        except Exception as e:
            self.logger.error(f"Failed to store processing result: {e}")
            return None
    
    def _insert_document(self, cursor, result: ProcessingResult) -> Optional[int]:
        """Insert document metadata"""
        try:
            sql = """
            INSERT INTO auction_docs (
                notice_id, file_name, file_path, page_count,
                pdf_type, pdf_type_confidence, processing_method,
                title, document_type, language,
                total_sections, total_blocks, processing_confidence,
                extraction_status, unknown_sections_count, 
                low_confidence_sections_count, validation_errors,
                processed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (notice_id, file_name) 
            DO UPDATE SET
                pdf_type = EXCLUDED.pdf_type,
                pdf_type_confidence = EXCLUDED.pdf_type_confidence,
                processing_method = EXCLUDED.processing_method,
                processing_confidence = EXCLUDED.processing_confidence,
                extraction_status = EXCLUDED.extraction_status,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id;
            """
            
            # Extract metadata
            pdf_type = 'digital' if result.pdf_type_result.is_digital else 'scanned'
            processing_method = result.pdf_type_result.processing_method
            
            # Calculate statistics
            total_sections = len(result.extracted_sections)
            unknown_sections = len([s for s in result.extracted_sections if s.header.normalized_label == 'UNKNOWN'])
            low_confidence_sections = len([s for s in result.extracted_sections if s.confidence < 0.5])
            
            # Get document metadata
            doc_metadata = result.processing_metadata.get('pdf_processing', {})
            title = result.pdf_type_result.sample_text[:100] if result.pdf_type_result.sample_text else None
            
            cursor.execute(sql, (
                result.notice_id,
                result.file_name,
                f"downloads/notice_{result.notice_id}/{result.file_name}",  # Reconstructed path
                result.pdf_type_result.total_pages,
                pdf_type,
                result.pdf_type_result.confidence,
                processing_method,
                title,
                'asset_sale_notice',  # Default type
                'korean',
                total_sections,
                sum(len(s.content_blocks) for s in result.extracted_sections),
                result.evidence_report.get('summary', {}).get('overall_confidence', 0.0),
                'completed' if result.success else 'failed',
                unknown_sections,
                low_confidence_sections,
                json.dumps([], ensure_ascii=False),  # validation_errors
                datetime.now()
            ))
            
            row = cursor.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            self.logger.error(f"Failed to insert document: {e}")
            return None
    
    def _insert_section(self, cursor, document_id: int, section, result: ProcessingResult) -> Optional[int]:
        """Insert section data"""
        try:
            sql = """
            INSERT INTO auction_sections (
                document_id, section_order, section_id,
                header_text, header_bbox, section_label, section_type, content_type,
                raw_content, content, confidence, evidence,
                validation_status, validation_errors,
                block_count, character_count, merge_history,
                cross_page_continuation, has_dates, has_money,
                has_phone, has_tables, has_registration_numbers
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            RETURNING id;
            """
            
            # Get content analysis
            content_analysis = result.content_analyses.get(section.section_id)
            content_type = content_analysis.content_type if content_analysis else 'UNKNOWN'
            
            # Prepare content JSON
            raw_content = " ".join(block.text for block in section.content_blocks)
            content_json = {
                'raw': raw_content,
                'normalized': {},  # Will be updated with fields
                'evidence': result.evidence_report
            }
            
            # Prepare evidence JSON
            evidence_json = {
                'header_detection': {
                    'method': 'rule_based',
                    'confidence': section.header.header_score,
                    'pattern_matched': section.header.pattern_matched,
                    'evidence': section.header.evidence
                },
                'content_classification': content_analysis.evidence if content_analysis else [],
                'boundary_detection': {
                    'merge_history': section.merge_history,
                    'cross_page': section.cross_page_continuation
                }
            }
            
            # Header bounding box
            header_bbox = {
                'page': section.header.block.page,
                'x0': section.header.block.bbox[0],
                'y0': section.header.block.bbox[1],
                'x1': section.header.block.bbox[2],
                'y1': section.header.block.bbox[3]
            }
            
            # Content characteristics
            characteristics = content_analysis.characteristics if content_analysis else {}
            
            cursor.execute(sql, (
                document_id,
                0,  # section_order - will be updated
                section.section_id,
                section.header.block.text,
                json.dumps(header_bbox, ensure_ascii=False),
                section.header.normalized_label,
                section.header.section_type,
                content_type,
                raw_content,
                json.dumps(content_json, ensure_ascii=False),
                section.confidence,
                json.dumps(evidence_json, ensure_ascii=False),
                'valid',  # validation_status
                json.dumps([], ensure_ascii=False),  # validation_errors
                len(section.content_blocks),
                len(raw_content),
                json.dumps(section.merge_history, ensure_ascii=False),
                section.cross_page_continuation,
                characteristics.get('has_dates', False),
                characteristics.get('has_money', False),
                characteristics.get('has_phone', False),
                characteristics.get('has_tables', False),
                characteristics.get('has_registration_numbers', False)
            ))
            
            row = cursor.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            self.logger.error(f"Failed to insert section: {e}")
            return None
    
    def _update_section_with_fields(self, cursor, section_id: int, 
                                   normalized_fields: Dict[str, Any]):
        """Update section with normalized fields"""
        try:
            # Prepare normalized data
            normalized_data = {}
            for field_name, normalized_field in normalized_fields.items():
                # Handle datetime serialization
                normalized_value = normalized_field.normalized_value
                if hasattr(normalized_value, 'isoformat'):  # datetime object
                    normalized_value = normalized_value.isoformat()
                
                normalized_data[field_name] = {
                    'original_value': normalized_field.original_value,
                    'normalized_value': normalized_value,
                    'data_type': normalized_field.data_type,
                    'confidence': normalized_field.confidence,
                    'validation_status': normalized_field.validation_status,
                    'validation_errors': normalized_field.validation_errors
                }
            
            # Update content JSON
            sql = """
            UPDATE auction_sections 
            SET content = jsonb_set(content, '{normalized}', %s::jsonb)
            WHERE id = %s;
            """
            
            cursor.execute(sql, (
                json.dumps(normalized_data, ensure_ascii=False),
                section_id
            ))
            
        except Exception as e:
            self.logger.error(f"Failed to update section with fields: {e}")
    
    def _update_document_statistics(self, cursor, document_id: int, result: ProcessingResult):
        """Update document statistics"""
        try:
            # The trigger will handle most statistics, but we can update specific ones
            pass
            
        except Exception as e:
            self.logger.error(f"Failed to update document statistics: {e}")
    
    def get_processing_summary(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get processing summary"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM auction_processing_summary ORDER BY processed_at DESC LIMIT %s;"
                    cur.execute(sql, (limit,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get processing summary: {e}")
            return []
    
    def search_sections(self, search_term: str, section_type: Optional[str] = None, 
                       limit: int = 50) -> List[Dict[str, Any]]:
        """Search sections by content"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    if section_type:
                        sql = """
                        SELECT s.document_id, d.notice_id, s.section_label, s.section_type,
                               s.header_text, LEFT(s.raw_content, 200) as content_snippet,
                               s.confidence
                        FROM auction_sections s
                        JOIN auction_docs d ON s.document_id = d.id
                        WHERE s.section_type = %s AND s.raw_content ILIKE %s
                        ORDER BY s.confidence DESC
                        LIMIT %s;
                        """
                        cur.execute(sql, (section_type, f'%{search_term}%', limit))
                    else:
                        sql = """
                        SELECT s.document_id, d.notice_id, s.section_label, s.section_type,
                               s.header_text, LEFT(s.raw_content, 200) as content_snippet,
                               s.confidence
                        FROM auction_sections s
                        JOIN auction_docs d ON s.document_id = d.id
                        WHERE s.raw_content ILIKE %s
                        ORDER BY s.confidence DESC
                        LIMIT %s;
                        """
                        cur.execute(sql, (f'%{search_term}%', limit))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to search sections: {e}")
            return []
    
    def get_review_queue(self, confidence_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Get sections that need review"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM get_review_queue(%s);"
                    cur.execute(sql, (confidence_threshold,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get review queue: {e}")
            return []
    
    def get_document_by_notice(self, notice_id: str) -> Optional[Dict[str, Any]]:
        """Get document by notice ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = "SELECT * FROM auction_docs WHERE notice_id = %s ORDER BY processed_at DESC LIMIT 1;"
                    cur.execute(sql, (notice_id,))
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Failed to get document: {e}")
            return None
    
    def get_sections_by_document(self, document_id: int) -> List[Dict[str, Any]]:
        """Get all sections for a document"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    sql = """
                    SELECT * FROM auction_sections 
                    WHERE document_id = %s 
                    ORDER BY section_order, id;
                    """
                    cur.execute(sql, (document_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get sections: {e}")
            return []
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get overall quality metrics"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Overall statistics
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_documents,
                            AVG(processing_confidence) as avg_confidence,
                            COUNT(*) FILTER (WHERE extraction_status = 'completed') as completed_docs,
                            COUNT(*) FILTER (WHERE extraction_status = 'failed') as failed_docs
                        FROM auction_docs;
                    """)
                    doc_stats = cur.fetchone()
                    
                    # Section statistics
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_sections,
                            AVG(confidence) as avg_section_confidence,
                            COUNT(*) FILTER (WHERE section_label = 'UNKNOWN') as unknown_sections,
                            COUNT(*) FILTER (WHERE confidence < 0.5) as low_confidence_sections
                        FROM auction_sections;
                    """)
                    section_stats = cur.fetchone()
                    
                    return {
                        'documents': {
                            'total': doc_stats[0],
                            'avg_confidence': doc_stats[1] or 0.0,
                            'completed': doc_stats[2],
                            'failed': doc_stats[3]
                        },
                        'sections': {
                            'total': section_stats[0],
                            'avg_confidence': section_stats[1] or 0.0,
                            'unknown': section_stats[2],
                            'low_confidence': section_stats[3]
                        }
                    }
        except Exception as e:
            self.logger.error(f"Failed to get quality metrics: {e}")
            return {}
    
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