"""
PDF batch processor that orchestrates parsing and database storage
"""
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from utils.logger import setup_logger
from database.database_manager import DatabaseManager
from .pdf_parser import PDFParser
from .content_structurer import ContentStructurer, StructuringResult
from .dynamic_section_processor import DynamicSectionProcessor, ProcessingResult


class PDFProcessor:
    """Orchestrates PDF processing and database storage"""
    
    def __init__(self, downloads_dir: str = "downloads", 
                 extracted_images_dir: str = "extracted_images"):
        self.logger = setup_logger(__name__)
        self.downloads_dir = downloads_dir
        self.extracted_images_dir = extracted_images_dir
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.pdf_parser = PDFParser(output_dir=extracted_images_dir)
        self.content_structurer = ContentStructurer()
        self.dynamic_processor = DynamicSectionProcessor()
        
        # Processing statistics
        self.stats = {
            'processed_files': 0,
            'failed_files': 0,
            'total_text_blocks': 0,
            'total_tables': 0,
            'total_images': 0
        }
    
    def initialize_database(self) -> bool:
        """Initialize database schema"""
        return self.db_manager.initialize_database()
    
    def test_connections(self) -> bool:
        """Test database connection"""
        return self.db_manager.test_connection()
    
    def process_all_pdfs(self, max_files: Optional[int] = None) -> Dict[str, Any]:
        """
        Process all PDF files in downloads directory
        
        Args:
            max_files: Maximum number of files to process (None for all)
            
        Returns:
            Processing statistics
        """
        self.logger.info("Starting batch PDF processing")
        
        # Find all PDF files
        pdf_files = self._find_pdf_files()
        
        if max_files:
            pdf_files = pdf_files[:max_files]
        
        self.logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Process each PDF file
        for pdf_info in pdf_files:
            success = self.process_pdf_file(
                pdf_info['file_path'], 
                pdf_info['notice_id']
            )
            
            if success:
                self.stats['processed_files'] += 1
            else:
                self.stats['failed_files'] += 1
        
        # Log final statistics
        self.logger.info(f"PDF processing completed: {self.stats}")
        
        return self.stats.copy()
    
    def process_pdf_file(self, pdf_path: str, notice_id: str) -> bool:
        """
        Process a single PDF file
        
        Args:
            pdf_path: Path to PDF file
            notice_id: Notice ID for the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Processing PDF: {pdf_path}")
            
            # Check if file exists
            if not os.path.exists(pdf_path):
                self.logger.error(f"PDF file not found: {pdf_path}")
                return False
            
            # Check if already processed
            file_name = os.path.basename(pdf_path)
            existing_doc = self.db_manager.get_document_by_notice_and_name(notice_id, file_name)
            
            if existing_doc:
                self.logger.info(f"PDF already processed: {file_name}")
                return True
            
            # Parse PDF
            parsed_data = self.pdf_parser.parse_pdf(pdf_path, notice_id)
            
            if not parsed_data:
                self.logger.error(f"Failed to parse PDF: {pdf_path}")
                return False
            
            # Store in database
            success = self._store_parsed_data(parsed_data)
            
            if success:
                # Update statistics
                self.stats['total_text_blocks'] += len(parsed_data['text_blocks'])
                self.stats['total_tables'] += len(parsed_data['tables'])
                self.stats['total_images'] += len(parsed_data['images'])
                
                # Extract both structured content and dynamic sections
                try:
                    document_id = self._get_document_id(notice_id, file_name)
                    if document_id:
                        # Legacy structured content extraction
                        self._extract_and_store_structured_content(document_id, notice_id, file_name, parsed_data)
                        
                        # New dynamic section processing
                        self._extract_and_store_dynamic_sections(document_id, notice_id, file_name, parsed_data)
                    else:
                        self.logger.warning(f"Could not find document ID for content extraction: {file_name}")
                except Exception as e:
                    self.logger.error(f"Content extraction failed for {file_name}: {e}")
                
                self.logger.info(f"Successfully processed PDF: {file_name}")
            else:
                self.logger.error(f"Failed to store PDF data: {file_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
            return False
    
    def _find_pdf_files(self) -> List[Dict[str, str]]:
        """Find all PDF files in downloads directory"""
        pdf_files = []
        
        try:
            downloads_path = Path(self.downloads_dir)
            
            if not downloads_path.exists():
                self.logger.warning(f"Downloads directory not found: {self.downloads_dir}")
                return pdf_files
            
            # Look for PDF files in subdirectories
            for notice_dir in downloads_path.iterdir():
                if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
                    # Extract notice ID from directory name
                    try:
                        notice_id = notice_dir.name.split('_')[1]
                    except IndexError:
                        self.logger.warning(f"Cannot extract notice ID from: {notice_dir.name}")
                        continue
                    
                    # Find PDF files in this notice directory
                    for file_path in notice_dir.glob('*.pdf'):
                        pdf_files.append({
                            'file_path': str(file_path),
                            'notice_id': notice_id,
                            'file_name': file_path.name
                        })
            
            self.logger.info(f"Found {len(pdf_files)} PDF files")
            
        except Exception as e:
            self.logger.error(f"Error finding PDF files: {e}")
        
        return pdf_files
    
    def _store_parsed_data(self, parsed_data: Dict[str, Any]) -> bool:
        """Store parsed PDF data in database"""
        try:
            pdf_info = parsed_data['pdf_info']
            
            # Insert document record
            document_id = self.db_manager.insert_pdf_document(
                notice_id=pdf_info['notice_id'],
                file_path=pdf_info['file_path'],
                file_name=pdf_info['file_name'],
                file_size=pdf_info['file_size'],
                page_count=pdf_info['page_count']
            )
            
            if not document_id:
                self.logger.error("Failed to insert PDF document record")
                return False
            
            # Insert text content
            for text_block in parsed_data['text_blocks']:
                success = self.db_manager.insert_text_content(
                    document_id=document_id,
                    page_number=text_block.page_number,
                    text_content=text_block.text,
                    bbox=text_block.bbox,
                    font_size=text_block.font_size,
                    font_name=text_block.font_name
                )
                
                if not success:
                    self.logger.warning(f"Failed to insert text block on page {text_block.page_number}")
            
            # Insert table data
            for table in parsed_data['tables']:
                success = self.db_manager.insert_table_data(
                    document_id=document_id,
                    page_number=table.page_number,
                    table_index=table.table_index,
                    table_data=table.data,
                    bbox=table.bbox
                )
                
                if not success:
                    self.logger.warning(f"Failed to insert table {table.table_index} on page {table.page_number}")
            
            # Insert image data
            for image in parsed_data['images']:
                success = self.db_manager.insert_image_data(
                    document_id=document_id,
                    page_number=image.page_number,
                    image_index=image.image_index,
                    image_path=image.image_path,
                    width=image.width,
                    height=image.height,
                    format_type=image.format_type,
                    file_size=image.file_size,
                    bbox=image.bbox
                )
                
                if not success:
                    self.logger.warning(f"Failed to insert image {image.image_index} on page {image.page_number}")
            
            self.logger.info(f"Stored data for document ID: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing parsed data: {e}")
            return False
    
    def process_specific_notice(self, notice_id: str) -> Dict[str, Any]:
        """Process PDFs for a specific notice ID"""
        self.logger.info(f"Processing PDFs for notice ID: {notice_id}")
        
        notice_stats = {
            'notice_id': notice_id,
            'processed_files': 0,
            'failed_files': 0,
            'files': []
        }
        
        # Find PDF files for this notice
        notice_dir = Path(self.downloads_dir) / f"notice_{notice_id}"
        
        if not notice_dir.exists():
            self.logger.warning(f"Notice directory not found: {notice_dir}")
            return notice_stats
        
        # Process all PDF files in the notice directory
        for pdf_file in notice_dir.glob('*.pdf'):
            success = self.process_pdf_file(str(pdf_file), notice_id)
            
            file_info = {
                'file_name': pdf_file.name,
                'success': success
            }
            
            notice_stats['files'].append(file_info)
            
            if success:
                notice_stats['processed_files'] += 1
            else:
                notice_stats['failed_files'] += 1
        
        self.logger.info(f"Notice {notice_id} processing completed: {notice_stats}")
        return notice_stats
    
    def get_processing_summary(self) -> List[Dict[str, Any]]:
        """Get processing summary from database"""
        return self.db_manager.get_processing_summary()
    
    def search_pdf_content(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search PDF content in database"""
        return self.db_manager.search_text_content(search_term, limit)
    
    def cleanup_failed_processing(self, notice_id: str, file_name: str) -> bool:
        """Clean up data for failed processing"""
        try:
            # Get document record
            doc = self.db_manager.get_document_by_notice_and_name(notice_id, file_name)
            
            if doc:
                # Delete document and all related data
                success = self.db_manager.delete_document_data(doc['id'])
                
                if success:
                    self.logger.info(f"Cleaned up data for {file_name}")
                    
                    # Also clean up extracted images
                    self._cleanup_extracted_images(notice_id, file_name)
                    
                return success
            else:
                self.logger.info(f"No data found to clean up for {file_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error cleaning up failed processing: {e}")
            return False
    
    def _cleanup_extracted_images(self, notice_id: str, file_name: str):
        """Clean up extracted image files"""
        try:
            image_dir = Path(self.extracted_images_dir)
            
            # Find images for this notice and file
            pattern = f"notice_{notice_id}_*"
            
            for image_file in image_dir.glob(pattern):
                try:
                    image_file.unlink()
                    self.logger.debug(f"Deleted extracted image: {image_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete image {image_file}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up extracted images: {e}")
    
    async def process_all_pdfs_async(self, max_concurrent: int = 3, 
                                   max_files: Optional[int] = None) -> Dict[str, Any]:
        """
        Process all PDFs asynchronously with concurrency control
        
        Args:
            max_concurrent: Maximum concurrent processing tasks
            max_files: Maximum number of files to process
            
        Returns:
            Processing statistics
        """
        self.logger.info(f"Starting async PDF processing with {max_concurrent} concurrent tasks")
        
        # Find PDF files
        pdf_files = self._find_pdf_files()
        
        if max_files:
            pdf_files = pdf_files[:max_files]
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Process files concurrently
        tasks = [
            self._process_pdf_async(semaphore, pdf_info['file_path'], pdf_info['notice_id'])
            for pdf_info in pdf_files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful
        
        self.stats['processed_files'] += successful
        self.stats['failed_files'] += failed
        
        self.logger.info(f"Async PDF processing completed: {successful} success, {failed} failed")
        
        return self.stats.copy()
    
    async def _process_pdf_async(self, semaphore: asyncio.Semaphore, 
                               pdf_path: str, notice_id: str) -> bool:
        """Process single PDF file asynchronously"""
        async with semaphore:
            # Run the synchronous processing in a thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self.process_pdf_file, 
                pdf_path, 
                notice_id
            )
    
    def _get_document_id(self, notice_id: str, file_name: str) -> Optional[int]:
        """Get document ID from database"""
        try:
            doc = self.db_manager.get_document_by_notice_and_name(notice_id, file_name)
            return doc['id'] if doc else None
        except Exception as e:
            self.logger.error(f"Error getting document ID for {file_name}: {e}")
            return None
    
    def _extract_and_store_structured_content(self, document_id: int, notice_id: str, 
                                            file_name: str, parsed_data: Dict[str, Any]):
        """Extract structured content and store in database"""
        try:
            self.logger.info(f"Extracting structured content for {file_name}")
            
            # Prepare text blocks for structuring
            text_blocks = [block.text for block in parsed_data['text_blocks']]
            
            # Prepare tables for structuring
            tables = []
            for table in parsed_data['tables']:
                tables.append({
                    'data': table.data,
                    'page_number': table.page_number,
                    'bbox': table.bbox
                })
            
            # Extract structured content
            result = self.content_structurer.structure_document(
                notice_id, file_name, text_blocks, tables
            )
            
            if result.success:
                # Store structured content in database
                success = self.db_manager.update_structured_content(
                    document_id=document_id,
                    structured_data=result.structured_data,
                    status='completed'
                )
                
                if success:
                    self.logger.info(f"Stored structured content for {file_name} (confidence: {result.confidence_score:.2f})")
                else:
                    self.logger.error(f"Failed to store structured content for {file_name}")
            else:
                # Store error status
                self.db_manager.update_structured_content(
                    document_id=document_id,
                    structured_data=None,
                    status='failed',
                    error_message=result.error_message
                )
                self.logger.error(f"Structured content extraction failed for {file_name}: {result.error_message}")
                
        except Exception as e:
            # Store error status
            self.db_manager.update_structured_content(
                document_id=document_id,
                structured_data=None,
                status='failed',
                error_message=str(e)
            )
            self.logger.error(f"Error extracting structured content for {file_name}: {e}")
    
    def process_structured_content_batch(self, limit: int = 10) -> Dict[str, Any]:
        """Process structured content for documents that don't have it yet"""
        self.logger.info("Starting batch structured content processing")
        
        # Get documents that need structured content extraction
        documents = self.db_manager.get_documents_for_structuring(limit)
        
        if not documents:
            self.logger.info("No documents need structured content processing")
            return {
                'processed_docs': 0,
                'failed_docs': 0,
                'message': 'No documents to process'
            }
        
        processed_count = 0
        failed_count = 0
        
        for doc in documents:
            try:
                self.logger.info(f"Processing structured content for document ID {doc['id']}: {doc['file_name']}")
                
                # Update status to processing
                self.db_manager.update_structured_content(
                    document_id=doc['id'],
                    structured_data=None,
                    status='processing'
                )
                
                # Get text blocks for this document
                text_blocks = self._get_text_blocks_for_document(doc['id'])
                tables = self._get_tables_for_document(doc['id'])
                
                # Extract structured content
                result = self.content_structurer.structure_document(
                    doc['notice_id'], doc['file_name'], text_blocks, tables
                )
                
                if result.success:
                    success = self.db_manager.update_structured_content(
                        document_id=doc['id'],
                        structured_data=result.structured_data,
                        status='completed'
                    )
                    
                    if success:
                        processed_count += 1
                        self.logger.info(f"Successfully processed structured content for {doc['file_name']} (confidence: {result.confidence_score:.2f})")
                    else:
                        failed_count += 1
                        self.logger.error(f"Failed to store structured content for {doc['file_name']}")
                else:
                    self.db_manager.update_structured_content(
                        document_id=doc['id'],
                        structured_data=None,
                        status='failed',
                        error_message=result.error_message
                    )
                    failed_count += 1
                    self.logger.error(f"Structured extraction failed for {doc['file_name']}: {result.error_message}")
                    
            except Exception as e:
                self.db_manager.update_structured_content(
                    document_id=doc['id'],
                    structured_data=None,
                    status='failed',
                    error_message=str(e)
                )
                failed_count += 1
                self.logger.error(f"Error processing structured content for {doc['file_name']}: {e}")
        
        result = {
            'processed_docs': processed_count,
            'failed_docs': failed_count,
            'total_docs': len(documents)
        }
        
        self.logger.info(f"Batch structured content processing completed: {result}")
        return result
    
    def _get_text_blocks_for_document(self, document_id: int) -> List[str]:
        """Get text blocks for a document from database"""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    SELECT text_content FROM pdf_text_content 
                    WHERE document_id = %s 
                    ORDER BY page_number, bbox_y0 DESC, bbox_x0 ASC;
                    """
                    cur.execute(sql, (document_id,))
                    rows = cur.fetchall()
                    
                    return [row[0] for row in rows if row[0] and row[0].strip()]
                    
        except Exception as e:
            self.logger.error(f"Error getting text blocks for document {document_id}: {e}")
            return []
    
    def _get_tables_for_document(self, document_id: int) -> List[Dict]:
        """Get tables for a document from database"""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    SELECT table_data, page_number, bbox_x0, bbox_y0, bbox_x1, bbox_y1
                    FROM pdf_tables 
                    WHERE document_id = %s 
                    ORDER BY page_number, table_index;
                    """
                    cur.execute(sql, (document_id,))
                    rows = cur.fetchall()
                    
                    tables = []
                    for row in rows:
                        table_data_json = row[0]
                        if isinstance(table_data_json, str):
                            import json
                            table_data = json.loads(table_data_json)
                        else:
                            table_data = table_data_json
                        
                        tables.append({
                            'data': table_data.get('rows', []),
                            'page_number': row[1],
                            'bbox': (row[2], row[3], row[4], row[5]) if row[2] is not None else None
                        })
                    
                    return tables
                    
        except Exception as e:
            self.logger.error(f"Error getting tables for document {document_id}: {e}")
            return []
    
    def get_structured_content_summary(self) -> List[Dict[str, Any]]:
        """Get structured content processing summary"""
        return self.db_manager.get_structured_content_summary()
    
    def search_structured_content(self, search_term: str, section: str = None) -> List[Dict[str, Any]]:
        """Search in structured content"""
        return self.db_manager.search_structured_content(search_term, section)
    
    def get_assets_by_type(self, asset_type: str) -> List[Dict[str, Any]]:
        """Get assets by type from structured content"""
        return self.db_manager.get_assets_by_type(asset_type)
    
    def _extract_and_store_dynamic_sections(self, document_id: int, notice_id: str, 
                                           file_name: str, parsed_data: Dict[str, Any]):
        """Extract dynamic sections and store in database"""
        try:
            self.logger.info(f"Extracting dynamic sections for {file_name}")
            
            # Prepare text blocks for processing
            text_blocks = [block.text for block in parsed_data['text_blocks']]
            
            # Prepare tables with metadata
            tables = []
            for table in parsed_data['tables']:
                tables.append({
                    'data': table.data,
                    'page_number': table.page_number,
                    'table_index': table.table_index,
                    'bbox': table.bbox
                })
            
            # Prepare images with metadata
            images = []
            for image in parsed_data['images']:
                images.append({
                    'page_number': image.page_number,
                    'image_index': image.image_index,
                    'image_path': image.image_path,
                    'width': image.width,
                    'height': image.height,
                    'format_type': image.format_type,
                    'bbox': image.bbox
                })
            
            # Process dynamic sections
            result = self.dynamic_processor.process_document(
                notice_id, file_name, text_blocks, tables, images
            )
            
            # Store result in database
            success = self.db_manager.store_dynamic_sections(document_id, result)
            
            if success:
                self.logger.info(f"Stored dynamic sections for {file_name} (confidence: {result.confidence_score:.2f})")
            else:
                self.logger.error(f"Failed to store dynamic sections for {file_name}")
                
        except Exception as e:
            self.logger.error(f"Error extracting dynamic sections for {file_name}: {e}")
    
    def process_dynamic_sections_batch(self, limit: int = 10) -> Dict[str, Any]:
        """Process dynamic sections for documents that don't have them yet"""
        self.logger.info("Starting batch dynamic section processing")
        
        # Get documents that need dynamic section processing
        documents = self.db_manager.get_documents_for_dynamic_processing(limit)
        
        if not documents:
            self.logger.info("No documents need dynamic section processing")
            return {
                'processed_docs': 0,
                'failed_docs': 0,
                'message': 'No documents to process'
            }
        
        processed_count = 0
        failed_count = 0
        
        for doc in documents:
            try:
                self.logger.info(f"Processing dynamic sections for document ID {doc['id']}: {doc['file_name']}")
                
                # Update status to processing
                self.db_manager.store_dynamic_sections(doc['id'], type('MockResult', (), {
                    'success': False,
                    'error_message': None,
                    'document_metadata': {},
                    'sections': {}
                })())
                
                # Get raw content for this document
                text_blocks = self._get_text_blocks_for_document(doc['id'])
                tables = self._get_tables_for_document(doc['id'])
                images = self._get_images_for_document(doc['id'])
                
                # Process dynamic sections
                result = self.dynamic_processor.process_document(
                    doc['notice_id'], doc['file_name'], text_blocks, tables, images
                )
                
                if result.success:
                    success = self.db_manager.store_dynamic_sections(doc['id'], result)
                    
                    if success:
                        processed_count += 1
                        self.logger.info(f"Successfully processed dynamic sections for {doc['file_name']} (confidence: {result.confidence_score:.2f})")
                    else:
                        failed_count += 1
                        self.logger.error(f"Failed to store dynamic sections for {doc['file_name']}")
                else:
                    # Store failed result
                    self.db_manager.store_dynamic_sections(doc['id'], result)
                    failed_count += 1
                    self.logger.error(f"Dynamic section processing failed for {doc['file_name']}: {result.error_message}")
                    
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error processing dynamic sections for {doc['file_name']}: {e}")
        
        result = {
            'processed_docs': processed_count,
            'failed_docs': failed_count,
            'total_docs': len(documents)
        }
        
        self.logger.info(f"Batch dynamic section processing completed: {result}")
        return result
    
    def _get_images_for_document(self, document_id: int) -> List[Dict]:
        """Get images for a document from database"""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    sql = """
                    SELECT page_number, image_index, image_path, width, height, format, 
                           bbox_x0, bbox_y0, bbox_x1, bbox_y1
                    FROM pdf_images 
                    WHERE document_id = %s 
                    ORDER BY page_number, image_index;
                    """
                    cur.execute(sql, (document_id,))
                    rows = cur.fetchall()
                    
                    images = []
                    for row in rows:
                        images.append({
                            'page_number': row[0],
                            'image_index': row[1],
                            'image_path': row[2],
                            'width': row[3],
                            'height': row[4],
                            'format_type': row[5],
                            'bbox': (row[6], row[7], row[8], row[9]) if row[6] is not None else None
                        })
                    
                    return images
                    
        except Exception as e:
            self.logger.error(f"Error getting images for document {document_id}: {e}")
            return []
    
    def get_dynamic_section_summary(self) -> List[Dict[str, Any]]:
        """Get dynamic section processing summary"""
        return self.db_manager.get_section_summary()
    
    def search_dynamic_sections(self, search_term: str, section_type: str = None) -> List[Dict[str, Any]]:
        """Search in dynamic sections"""
        return self.db_manager.search_sections(search_term, section_type)
    
    def get_sections_by_document(self, notice_id: str, file_name: str) -> List[Dict[str, Any]]:
        """Get all sections for a specific document"""
        return self.db_manager.get_sections_by_document(notice_id, file_name)