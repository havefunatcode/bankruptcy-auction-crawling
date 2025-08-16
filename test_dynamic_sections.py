#!/usr/bin/env python3
"""
Simple test for dynamic section functionality
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pdf_processing.pdf_processor import PDFProcessor
from utils.logger import setup_logger


def main():
    """Test dynamic section processing"""
    logger = setup_logger(__name__)
    logger.info("Testing dynamic section processing")
    
    # Initialize processor
    processor = PDFProcessor()
    
    # Test database connection
    if not processor.test_connections():
        logger.error("Database connection failed")
        return False
    
    # Get processing summary
    summary = processor.get_processing_summary()
    logger.info(f"Found {len(summary)} processed documents")
    
    if summary:
        # Show basic document info
        for doc in summary[:3]:  # Show first 3
            logger.info(f"Document: {doc.get('notice_id')} - {doc.get('file_name')}")
            logger.info(f"  Processing type: {doc.get('processing_type', 'unknown')}")
            logger.info(f"  Total sections: {doc.get('total_sections', 0)}")
    
    # Test dynamic section search if documents exist
    if summary:
        logger.info("Testing dynamic section search...")
        search_results = processor.search_dynamic_sections("매각")
        logger.info(f"Found {len(search_results)} sections containing '매각'")
        
        for i, result in enumerate(search_results[:3]):
            logger.info(f"  {i+1}. {result.get('notice_id')} - {result.get('section_name')[:50]}...")
    
    # Test getting sections for a specific document
    if summary:
        first_doc = summary[0]
        notice_id = first_doc.get('notice_id')
        file_name = first_doc.get('file_name')
        
        if notice_id and file_name:
            logger.info(f"Getting sections for document: {notice_id}")
            doc_sections = processor.get_sections_by_document(notice_id, file_name)
            logger.info(f"Found {len(doc_sections)} sections for this document")
            
            for section in doc_sections[:5]:  # Show first 5
                logger.info(f"  - {section.get('section_name')[:50]}... ({section.get('section_type')})")
    
    logger.info("Dynamic section test completed successfully")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)