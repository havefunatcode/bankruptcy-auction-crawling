#!/usr/bin/env python3
"""
Reset database and reprocess all PDFs with dynamic section system
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pdf_processing.pdf_processor import PDFProcessor
from database.database_manager import DatabaseManager
from utils.logger import setup_logger


def truncate_tables(db_manager: DatabaseManager) -> bool:
    """Truncate all PDF-related tables"""
    logger = setup_logger(__name__)
    
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                logger.info("Dropping and recreating PDF-related tables...")
                
                # Drop tables in dependency order
                tables_to_drop = [
                    'pdf_processing_results',
                    'pdf_section_images', 
                    'pdf_section_tables',
                    'pdf_subsections',
                    'pdf_sections',
                    'pdf_text_content',
                    'pdf_tables', 
                    'pdf_images',
                    'pdf_documents'
                ]
                
                for table in tables_to_drop:
                    try:
                        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                        logger.info(f"Dropped table: {table}")
                    except Exception as e:
                        logger.warning(f"Could not drop {table}: {e}")
                
                # Also drop views
                views_to_drop = [
                    'pdf_processing_summary',
                    'pdf_section_analysis', 
                    'pdf_section_search',
                    'pdf_structured_analysis'
                ]
                
                for view in views_to_drop:
                    try:
                        cur.execute(f"DROP VIEW IF EXISTS {view} CASCADE;")
                        logger.info(f"Dropped view: {view}")
                    except Exception as e:
                        logger.warning(f"Could not drop view {view}: {e}")
                
                # Drop functions
                functions_to_drop = [
                    'get_sections_by_type(VARCHAR)',
                    'search_section_content(TEXT)'
                ]
                
                for func in functions_to_drop:
                    try:
                        cur.execute(f"DROP FUNCTION IF EXISTS {func} CASCADE;")
                        logger.info(f"Dropped function: {func}")
                    except Exception as e:
                        logger.warning(f"Could not drop function {func}: {e}")
                
                conn.commit()
                logger.info("All tables, views, and functions dropped successfully")
                return True
                
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        return False


def apply_schema_extension(db_manager: DatabaseManager) -> bool:
    """Apply schema extension for dynamic sections"""
    logger = setup_logger(__name__)
    
    try:
        schema_file = project_root / "database" / "schema_extension.sql"
        if not schema_file.exists():
            logger.error("Schema extension file not found")
            return False
        
        logger.info("Applying schema extension...")
        
        with db_manager.get_connection() as conn:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                conn.commit()
        
        logger.info("Schema extension applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply schema extension: {e}")
        return False


def check_downloads_directory() -> bool:
    """Check if downloads directory exists and has PDF files"""
    logger = setup_logger(__name__)
    
    downloads_dir = project_root / "downloads"
    if not downloads_dir.exists():
        logger.error(f"Downloads directory not found: {downloads_dir}")
        return False
    
    # Count PDF files
    pdf_count = 0
    for notice_dir in downloads_dir.iterdir():
        if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
            pdf_files = list(notice_dir.glob('*.pdf'))
            pdf_count += len(pdf_files)
    
    logger.info(f"Found {pdf_count} PDF files in downloads directory")
    
    if pdf_count == 0:
        logger.warning("No PDF files found in downloads directory")
        return False
    
    return True


def main():
    """Main function to reset and reprocess all PDFs"""
    logger = setup_logger(__name__)
    logger.info("Starting database reset and reprocessing")
    
    # Initialize components
    db_manager = DatabaseManager()
    processor = PDFProcessor()
    
    # Test database connection
    if not db_manager.test_connection():
        logger.error("Database connection failed")
        return False
    
    # Check downloads directory
    if not check_downloads_directory():
        logger.error("Downloads directory check failed")
        return False
    
    # Step 1: Truncate tables
    logger.info("Step 1: Truncating database tables...")
    if not truncate_tables(db_manager):
        logger.error("Failed to truncate tables")
        return False
    
    # Step 2: Initialize base database schema first
    logger.info("Step 2: Initializing base database schema...")
    if not processor.initialize_database():
        logger.error("Failed to initialize database")
        return False
    
    # Step 3: Apply schema extension
    logger.info("Step 3: Applying schema extension...")
    if not apply_schema_extension(db_manager):
        logger.error("Failed to apply schema extension")
        return False
    
    # Step 4: Process all PDFs
    logger.info("Step 4: Processing all PDFs with new dynamic section system...")
    
    # Get list of all PDF files first
    pdf_files = []
    downloads_dir = Path("downloads")
    
    for notice_dir in downloads_dir.iterdir():
        if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
            for pdf_file in notice_dir.glob('*.pdf'):
                notice_id = notice_dir.name.split('_')[1]
                pdf_files.append({
                    'file_path': str(pdf_file),
                    'notice_id': notice_id,
                    'file_name': pdf_file.name
                })
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF
    processed = 0
    failed = 0
    
    for i, pdf_info in enumerate(pdf_files, 1):
        logger.info(f"Processing PDF {i}/{len(pdf_files)}: {pdf_info['file_name']}")
        
        success = processor.process_pdf_file(
            pdf_info['file_path'], 
            pdf_info['notice_id']
        )
        
        if success:
            processed += 1
            logger.info(f"✅ Successfully processed: {pdf_info['file_name']}")
        else:
            failed += 1
            logger.error(f"❌ Failed to process: {pdf_info['file_name']}")
    
    # Step 5: Show final statistics
    logger.info("Step 5: Final processing statistics")
    logger.info(f"📊 Processing Summary:")
    logger.info(f"   Total files: {len(pdf_files)}")
    logger.info(f"   Successfully processed: {processed}")
    logger.info(f"   Failed: {failed}")
    
    # Get database summary
    processing_summary = processor.get_processing_summary()
    logger.info(f"   Documents in database: {len(processing_summary)}")
    
    # Get dynamic section summary
    section_summary = processor.get_dynamic_section_summary()
    logger.info(f"   Documents with dynamic sections: {len(section_summary)}")
    
    if section_summary:
        total_sections = sum(row.get('tables_count', 0) + row.get('images_count', 0) + 1 
                           for row in section_summary)
        logger.info(f"   Total sections detected: {total_sections}")
        
        # Show section types
        section_types = {}
        for row in section_summary:
            section_type = row.get('section_type', 'unknown')
            section_types[section_type] = section_types.get(section_type, 0) + 1
        
        logger.info(f"   Section types distribution: {dict(section_types)}")
    
    # Process dynamic sections for all documents
    logger.info("Processing dynamic sections for all documents...")
    dynamic_result = processor.process_dynamic_sections_batch(limit=10)
    logger.info(f"Dynamic section processing result: {dynamic_result}")
    
    # Test search functionality
    logger.info("Testing search functionality...")
    search_results = processor.search_dynamic_sections("매각")
    logger.info(f"Found {len(search_results)} sections containing '매각'")
    
    logger.info("✅ Database reset and reprocessing completed successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)