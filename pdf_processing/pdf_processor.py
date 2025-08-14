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