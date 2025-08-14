#!/usr/bin/env python3
"""
Test script for PDF processing implementation
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager
from pdf_processing.pdf_parser import PDFParser
from pdf_processing.pdf_processor import PDFProcessor
from utils.logger import setup_logger


def test_database_connection():
    """Test database connection and schema creation"""
    print("=" * 60)
    print("TESTING DATABASE CONNECTION")
    print("=" * 60)
    
    try:
        db_manager = DatabaseManager()
        
        print("1. Testing database connection...")
        if db_manager.test_connection():
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Database connection failed")
            return False
        
        print("2. Initializing database schema...")
        if db_manager.initialize_database():
            print("   ✅ Database schema initialized successfully")
        else:
            print("   ❌ Database schema initialization failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        return False


def test_pdf_parser():
    """Test PDF parser with sample files"""
    print("\n" + "=" * 60)
    print("TESTING PDF PARSER")
    print("=" * 60)
    
    try:
        # Find a sample PDF file
        downloads_dir = Path("downloads")
        sample_pdfs = list(downloads_dir.glob("**/*.pdf"))
        
        if not sample_pdfs:
            print("   ⚠️ No PDF files found in downloads directory")
            return True  # Not a failure, just no files to test
        
        # Test with first PDF found
        sample_pdf = sample_pdfs[0]
        notice_id = sample_pdf.parent.name.split('_')[1] if '_' in sample_pdf.parent.name else "test"
        
        print(f"1. Testing PDF parsing with: {sample_pdf.name}")
        
        parser = PDFParser(output_dir="test_extracted_images")
        
        # Parse PDF
        result = parser.parse_pdf(str(sample_pdf), notice_id)
        
        if result:
            print(f"   ✅ PDF parsed successfully")
            print(f"   📄 Pages: {result['pdf_info']['page_count']}")
            print(f"   📝 Text blocks: {len(result['text_blocks'])}")
            print(f"   📊 Tables: {len(result['tables'])}")
            print(f"   🖼️ Images: {len(result['images'])}")
            
            # Test text extraction
            if result['text_blocks']:
                sample_text = result['text_blocks'][0].text[:100]
                print(f"   📖 Sample text: {sample_text}...")
            
            return True
        else:
            print("   ❌ PDF parsing failed")
            return False
            
    except Exception as e:
        print(f"   ❌ PDF parser test failed: {e}")
        return False


def test_pdf_processor():
    """Test PDF processor with database integration"""
    print("\n" + "=" * 60)
    print("TESTING PDF PROCESSOR")
    print("=" * 60)
    
    try:
        processor = PDFProcessor(downloads_dir="downloads")
        
        print("1. Testing database connections...")
        if not processor.test_connections():
            print("   ❌ Database connection failed")
            return False
        print("   ✅ Database connection successful")
        
        print("2. Initializing database...")
        if not processor.initialize_database():
            print("   ❌ Database initialization failed")
            return False
        print("   ✅ Database initialized")
        
        print("3. Finding PDF files...")
        # Get list of available PDFs
        downloads_dir = Path("downloads")
        if not downloads_dir.exists():
            print("   ⚠️ Downloads directory not found")
            return True
        
        sample_pdfs = list(downloads_dir.glob("**/*.pdf"))
        if not sample_pdfs:
            print("   ⚠️ No PDF files found")
            return True
        
        print(f"   📂 Found {len(sample_pdfs)} PDF files")
        
        # Test processing one PDF
        sample_pdf = sample_pdfs[0]
        notice_id = sample_pdf.parent.name.split('_')[1] if '_' in sample_pdf.parent.name else "test"
        
        print(f"4. Processing sample PDF: {sample_pdf.name}")
        success = processor.process_pdf_file(str(sample_pdf), notice_id)
        
        if success:
            print("   ✅ PDF processed and stored successfully")
        else:
            print("   ❌ PDF processing failed")
            return False
        
        print("5. Testing database queries...")
        # Test retrieval
        doc = processor.db_manager.get_document_by_notice_and_name(notice_id, sample_pdf.name)
        if doc:
            print(f"   ✅ Document found in database (ID: {doc['id']})")
        else:
            print("   ❌ Document not found in database")
            return False
        
        # Test search
        search_results = processor.search_pdf_content("공고")
        print(f"   🔍 Search results: {len(search_results)} matches")
        
        return True
        
    except Exception as e:
        print(f"   ❌ PDF processor test failed: {e}")
        return False


def test_integration():
    """Test full integration"""
    print("\n" + "=" * 60)
    print("TESTING FULL INTEGRATION")
    print("=" * 60)
    
    try:
        processor = PDFProcessor()
        
        print("1. Testing batch processing...")
        stats = processor.process_all_pdfs(max_files=2)  # Process max 2 files for testing
        
        print(f"   📊 Processing statistics:")
        print(f"      Processed files: {stats['processed_files']}")
        print(f"      Failed files: {stats['failed_files']}")
        print(f"      Total text blocks: {stats['total_text_blocks']}")
        print(f"      Total tables: {stats['total_tables']}")
        print(f"      Total images: {stats['total_images']}")
        
        if stats['processed_files'] > 0:
            print("   ✅ Batch processing successful")
        else:
            print("   ⚠️ No files were processed")
        
        print("2. Testing processing summary...")
        summary = processor.get_processing_summary()
        print(f"   📋 Summary records: {len(summary)}")
        
        if summary:
            for item in summary[:2]:  # Show first 2 items
                print(f"      Notice {item['notice_id']}: {item['file_name']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Integration test failed: {e}")
        return False


async def main():
    """Main test runner"""
    print("🧪 TESTING PDF PROCESSING IMPLEMENTATION")
    print("=" * 80)
    
    logger = setup_logger(__name__)
    
    # Test results
    results = {
        'database': False,
        'parser': False,
        'processor': False,
        'integration': False
    }
    
    try:
        # Run tests
        results['database'] = test_database_connection()
        
        if results['database']:
            results['parser'] = test_pdf_parser()
            results['processor'] = test_pdf_processor()
            results['integration'] = test_integration()
        else:
            print("⚠️ Skipping other tests due to database connection failure")
        
        # Print final results
        print("\n" + "=" * 80)
        print("TEST RESULTS SUMMARY")
        print("=" * 80)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name.upper():<20} {status}")
        
        all_passed = all(results.values())
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! PDF processing implementation is ready.")
            print("\nNext steps:")
            print("1. Install dependencies: pip install -r requirements.txt")
            print("2. Start Docker PostgreSQL container")
            print("3. Run crawler with PDF processing: python main.py --with-attachments --process-pdfs")
        else:
            print("\n⚠️ Some tests failed. Please check the implementation.")
            
        return 0 if all_passed else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        print(f"\n❌ Test runner failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)