#!/usr/bin/env python3
"""
Test script for dynamic section processing
"""
import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pdf_processing.pdf_processor import PDFProcessor
from utils.logger import setup_logger


def main():
    """Main function to test dynamic section processing"""
    logger = setup_logger(__name__)
    logger.info("Starting dynamic section processing test")
    
    # Initialize PDF processor
    processor = PDFProcessor()
    
    # Test database connection
    if not processor.test_connections():
        logger.error("Database connection failed")
        return False
    
    # Apply schema extension if needed
    try:
        logger.info("Checking database schema...")
        schema_file = project_root / "database" / "schema_extension.sql"
        if schema_file.exists():
            logger.info("Applying schema extension...")
            import subprocess
            result = subprocess.run([
                "psql", 
                "-h", "localhost",
                "-U", "postgres", 
                "-d", "bankruptcy_auction",
                "-f", str(schema_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Schema extension applied successfully")
            else:
                logger.warning(f"Schema extension failed: {result.stderr}")
        else:
            logger.warning("Schema extension file not found")
    except Exception as e:
        logger.warning(f"Could not apply schema extension: {e}")
    
    # Get processing summary
    logger.info("Getting processing summary...")
    summary = processor.get_processing_summary()
    logger.info(f"Found {len(summary)} processed documents")
    
    # Process dynamic sections for documents that need it
    logger.info("Processing dynamic sections...")
    result = processor.process_dynamic_sections_batch(limit=5)
    
    logger.info(f"Dynamic section processing result: {result}")
    
    # Get dynamic section summary
    logger.info("Getting dynamic section summary...")
    section_summary = processor.get_dynamic_section_summary()
    logger.info(f"Found {len(section_summary)} documents with dynamic sections")
    
    # Show some example sections
    if section_summary:
        logger.info("Example sections:")
        for i, section in enumerate(section_summary[:3]):  # Show first 3
            logger.info(f"  {i+1}. {section.get('notice_id')} - {section.get('file_name')}")
            logger.info(f"     Section: {section.get('section_name')} ({section.get('section_type')})")
            logger.info(f"     Content length: {section.get('content_length')} chars")
    
    # Test search functionality
    logger.info("Testing section search...")
    search_results = processor.search_dynamic_sections("매각", limit=3)
    logger.info(f"Found {len(search_results)} sections matching '매각'")
    
    for i, result in enumerate(search_results[:2]):  # Show first 2
        logger.info(f"  {i+1}. {result.get('notice_id')} - {result.get('section_name')}")
        logger.info(f"     Relevance: {result.get('relevance', 0):.3f}")
    
    # Test document sections retrieval
    if section_summary:
        first_doc = section_summary[0]
        notice_id = first_doc.get('notice_id')
        file_name = first_doc.get('file_name')
        
        if notice_id and file_name:
            logger.info(f"Getting sections for document: {notice_id} - {file_name}")
            doc_sections = processor.get_sections_by_document(notice_id, file_name)
            logger.info(f"Found {len(doc_sections)} sections for this document")
            
            for section in doc_sections[:3]:  # Show first 3 sections
                logger.info(f"  - {section.get('section_name')} ({section.get('section_type')})")
                logger.info(f"    Tables: {section.get('tables_count')}, Images: {section.get('images_count')}")
    
    logger.info("Dynamic section processing test completed successfully")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)