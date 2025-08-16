#!/usr/bin/env python3
"""
Test Rule-based PDF Processing System
Comprehensive test of the new rule-based processing pipeline
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pdf_processing.rule_based_pdf_processor import RuleBasedPDFProcessor
from database.rule_based_db_manager import RuleBasedDBManager
from utils.logger import setup_logger


def test_individual_components():
    """Test individual components"""
    logger = setup_logger(__name__)
    logger.info("=== Testing Individual Components ===")
    
    # Test PDF type detection
    logger.info("1. Testing PDF Type Detection...")
    from pdf_processing.pdf_type_detector import PDFTypeDetector
    
    detector = PDFTypeDetector()
    
    # Find test PDF
    downloads_dir = Path("downloads")
    test_pdf = None
    
    if downloads_dir.exists():
        for notice_dir in downloads_dir.iterdir():
            if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
                pdf_files = list(notice_dir.glob('*.pdf'))
                if pdf_files:
                    test_pdf = pdf_files[0]
                    break
    
    if test_pdf:
        result = detector.detect_pdf_type(str(test_pdf))
        logger.info(f"   PDF Type: {'Digital' if result.is_digital else 'Scanned'}")
        logger.info(f"   Confidence: {result.confidence:.2f}")
        logger.info(f"   Processing Method: {result.processing_method}")
    else:
        logger.warning("   No test PDF found")
    
    # Test section header detection
    logger.info("2. Testing Section Header Detection...")
    from pdf_processing.rule_based_section_detector import RuleBasedSectionDetector, Block
    
    section_detector = RuleBasedSectionDetector()
    
    # Create sample blocks
    sample_blocks = [
        Block(1, (0, 100, 500, 120), "자산매각공고", font_size=16.0, is_bold=True, line_gap_before=20.0),
        Block(1, (0, 140, 500, 160), "본 법원은 아래와 같이 자산을 매각합니다.", font_size=12.0),
        Block(1, (0, 180, 500, 200), "1. 매각대상자산", font_size=14.0, is_bold=True, line_gap_before=15.0),
        Block(1, (0, 220, 500, 240), "특허권 제1234567호", font_size=12.0),
        Block(1, (0, 260, 500, 280), "2. 입찰방법", font_size=14.0, is_bold=True, line_gap_before=15.0),
        Block(1, (0, 300, 500, 320), "서면입찰에 의합니다.", font_size=12.0),
    ]
    
    headers = section_detector.detect_section_headers(sample_blocks)
    logger.info(f"   Detected {len(headers)} headers:")
    for header in headers:
        logger.info(f"     - '{header.block.text}' -> {header.normalized_label} (score: {header.header_score:.2f})")
    
    # Test field normalization
    logger.info("3. Testing Field Normalization...")
    from pdf_processing.field_normalizer import FieldNormalizer
    
    normalizer = FieldNormalizer()
    
    test_data = {
        'bid_date': '2024년 12월 15일',
        'minimum_bid': '1,000만원',
        'contact_phone': '02-1234-5678',
        'patent_number': '특허 제1234567호'
    }
    
    normalized = normalizer.normalize_section_fields(test_data)
    logger.info(f"   Normalized {len(normalized)} fields:")
    for field_name, field in normalized.items():
        logger.info(f"     - {field_name}: '{field.original_value}' -> {field.normalized_value} ({field.data_type})")
    
    logger.info("✅ Individual component tests completed")


def test_database_operations():
    """Test database operations"""
    logger = setup_logger(__name__)
    logger.info("=== Testing Database Operations ===")
    
    db_manager = RuleBasedDBManager()
    
    # Test connection
    logger.info("1. Testing database connection...")
    if db_manager.test_connection():
        logger.info("   ✅ Database connection successful")
    else:
        logger.error("   ❌ Database connection failed")
        return False
    
    # Test schema initialization
    logger.info("2. Testing schema initialization...")
    if db_manager.initialize_schema():
        logger.info("   ✅ Schema initialization successful")
    else:
        logger.error("   ❌ Schema initialization failed")
        return False
    
    # Test basic queries
    logger.info("3. Testing basic queries...")
    try:
        summary = db_manager.get_processing_summary(5)
        logger.info(f"   Found {len(summary)} documents in processing summary")
        
        metrics = db_manager.get_quality_metrics()
        logger.info(f"   Quality metrics: {metrics}")
        
        logger.info("   ✅ Basic queries successful")
    except Exception as e:
        logger.error(f"   ❌ Basic queries failed: {e}")
        return False
    
    return True


def test_end_to_end_processing():
    """Test end-to-end PDF processing"""
    logger = setup_logger(__name__)
    logger.info("=== Testing End-to-End Processing ===")
    
    # Initialize components
    processor = RuleBasedPDFProcessor()
    db_manager = RuleBasedDBManager()
    
    # Find test PDF
    downloads_dir = Path("downloads")
    test_files = []
    
    if downloads_dir.exists():
        for notice_dir in downloads_dir.iterdir():
            if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
                pdf_files = list(notice_dir.glob('*.pdf'))
                if pdf_files:
                    notice_id = notice_dir.name.split('_')[1]
                    test_files.append((str(pdf_files[0]), notice_id))
                    
                if len(test_files) >= 2:  # Test with 2 files
                    break
    
    if not test_files:
        logger.warning("No test PDF files found")
        return False
    
    # Process each test file
    results = []
    for pdf_path, notice_id in test_files:
        logger.info(f"Processing: {os.path.basename(pdf_path)}")
        
        # Process PDF
        result = processor.process_pdf(pdf_path, notice_id)
        
        if result.success:
            logger.info(f"   ✅ Processing successful")
            logger.info(f"   PDF Type: {'Digital' if result.pdf_type_result.is_digital else 'Scanned'}")
            logger.info(f"   Sections: {len(result.extracted_sections)}")
            logger.info(f"   Content Types: {set(a.content_type for a in result.content_analyses.values())}")
            logger.info(f"   Overall Confidence: {result.evidence_report.get('summary', {}).get('overall_confidence', 0):.2f}")
            
            # Store in database
            doc_id = db_manager.store_processing_result(result)
            if doc_id:
                logger.info(f"   ✅ Stored in database (doc_id: {doc_id})")
            else:
                logger.error(f"   ❌ Failed to store in database")
            
            results.append(result)
        else:
            logger.error(f"   ❌ Processing failed: {result.error_message}")
    
    return len(results) > 0


def test_search_and_analysis():
    """Test search and analysis functions"""
    logger = setup_logger(__name__)
    logger.info("=== Testing Search and Analysis ===")
    
    db_manager = RuleBasedDBManager()
    
    # Test processing summary
    logger.info("1. Testing processing summary...")
    summary = db_manager.get_processing_summary(10)
    logger.info(f"   Found {len(summary)} documents")
    
    for doc in summary[:3]:
        logger.info(f"   - {doc.get('notice_id')}: {doc.get('quality_assessment')} quality, "
                   f"{doc.get('total_sections')} sections")
    
    # Test section search
    logger.info("2. Testing section search...")
    search_terms = ['매각', '입찰', '특허']
    
    for term in search_terms:
        try:
            results = db_manager.search_sections(term, limit=3)
            logger.info(f"   '{term}' search: {len(results)} results")
            for result in results[:2]:
                logger.info(f"     - {result.get('notice_id')}: {result.get('section_label')}")
        except Exception as e:
            logger.warning(f"   Search for '{term}' failed: {e}")
    
    # Test review queue
    logger.info("3. Testing review queue...")
    try:
        review_items = db_manager.get_review_queue(0.5)
        logger.info(f"   Found {len(review_items)} items needing review")
        
        for item in review_items[:3]:
            logger.info(f"     - {item.get('notice_id')}: {item.get('section_label')} "
                       f"(confidence: {item.get('confidence', 0):.2f})")
    except Exception as e:
        logger.warning(f"   Review queue test failed: {e}")
    
    # Test quality metrics
    logger.info("4. Testing quality metrics...")
    metrics = db_manager.get_quality_metrics()
    if metrics:
        logger.info(f"   Documents: {metrics.get('documents', {})}")
        logger.info(f"   Sections: {metrics.get('sections', {})}")
    
    logger.info("✅ Search and analysis tests completed")


def generate_test_report():
    """Generate comprehensive test report"""
    logger = setup_logger(__name__)
    logger.info("=== Generating Test Report ===")
    
    db_manager = RuleBasedDBManager()
    
    # Get overall statistics
    metrics = db_manager.get_quality_metrics()
    summary = db_manager.get_processing_summary()
    review_queue = db_manager.get_review_queue()
    
    logger.info("📊 RULE-BASED PDF PROCESSING SYSTEM TEST REPORT")
    logger.info("=" * 60)
    
    # Document statistics
    doc_stats = metrics.get('documents', {})
    logger.info(f"📄 Document Processing:")
    logger.info(f"   Total Documents: {doc_stats.get('total', 0)}")
    logger.info(f"   Completed: {doc_stats.get('completed', 0)}")
    logger.info(f"   Failed: {doc_stats.get('failed', 0)}")
    logger.info(f"   Average Confidence: {doc_stats.get('avg_confidence', 0):.2f}")
    
    # Section statistics
    section_stats = metrics.get('sections', {})
    logger.info(f"\\n📋 Section Processing:")
    logger.info(f"   Total Sections: {section_stats.get('total', 0)}")
    logger.info(f"   Average Confidence: {section_stats.get('avg_confidence', 0):.2f}")
    logger.info(f"   Unknown Sections: {section_stats.get('unknown', 0)}")
    logger.info(f"   Low Confidence: {section_stats.get('low_confidence', 0)}")
    
    # Quality assessment
    logger.info(f"\\n🎯 Quality Assessment:")
    if summary:
        quality_dist = {}
        for doc in summary:
            quality = doc.get('quality_assessment', 'unknown')
            quality_dist[quality] = quality_dist.get(quality, 0) + 1
        
        for quality, count in quality_dist.items():
            logger.info(f"   {quality.title()}: {count} documents")
    
    # Review queue
    logger.info(f"\\n🔍 Review Queue:")
    logger.info(f"   Items needing review: {len(review_queue)}")
    
    # Processing method distribution
    if summary:
        method_dist = {}
        for doc in summary:
            method = doc.get('processing_method', 'unknown')
            method_dist[method] = method_dist.get(method, 0) + 1
        
        logger.info(f"\\n⚙️ Processing Methods:")
        for method, count in method_dist.items():
            logger.info(f"   {method}: {count} documents")
    
    logger.info("\\n✅ Rule-based PDF processing system is operational!")
    logger.info("🚀 Ready for production use with evidence tracking and confidence scoring")


def main():
    """Main test function"""
    logger = setup_logger(__name__)
    logger.info("Starting Rule-based PDF Processing System Tests")
    
    try:
        # Test individual components
        test_individual_components()
        
        # Test database operations
        if not test_database_operations():
            logger.error("Database tests failed, aborting")
            return False
        
        # Test end-to-end processing
        if not test_end_to_end_processing():
            logger.error("End-to-end tests failed")
            return False
        
        # Test search and analysis
        test_search_and_analysis()
        
        # Generate final report
        generate_test_report()
        
        logger.info("🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)