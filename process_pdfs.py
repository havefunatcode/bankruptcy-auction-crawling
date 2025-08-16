#!/usr/bin/env python3
"""
Standalone PDF processing script for bankruptcy auction documents
"""
import asyncio
import argparse
import sys
import os
from pathlib import Path
from pdf_processing.pdf_processor import PDFProcessor
from utils.logger import setup_logger


def main():
    """Main entry point for PDF processing"""
    
    parser = argparse.ArgumentParser(description='Process PDF files and store in database')
    parser.add_argument('--downloads-dir', default='downloads', help='Directory containing PDF files')
    parser.add_argument('--notice-id', help='Process PDFs for specific notice ID only')
    parser.add_argument('--max-files', type=int, help='Maximum number of files to process')
    parser.add_argument('--test-db', action='store_true', help='Test database connection only')
    parser.add_argument('--init-db', action='store_true', help='Initialize database schema only')
    parser.add_argument('--search', help='Search PDF content in database')
    parser.add_argument('--summary', action='store_true', help='Show processing summary from database')
    parser.add_argument('--async-mode', action='store_true', help='Use async processing for better performance')
    parser.add_argument('--concurrent', type=int, default=3, help='Number of concurrent async tasks')
    
    # Structured content options
    parser.add_argument('--extract-structured', action='store_true', help='Extract structured content from existing PDFs')
    parser.add_argument('--structured-summary', action='store_true', help='Show structured content summary')
    parser.add_argument('--search-structured', help='Search in structured content')
    parser.add_argument('--assets-by-type', help='Get assets by type from structured content')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logger(__name__)
    
    try:
        # Initialize PDF processor
        processor = PDFProcessor(downloads_dir=args.downloads_dir)
        
        # Test database connection
        if args.test_db:
            print("Testing database connection...")
            if processor.test_connections():
                print("✅ Database connection successful")
                return 0
            else:
                print("❌ Database connection failed")
                return 1
        
        # Initialize database
        if args.init_db:
            print("Initializing database schema...")
            if processor.initialize_database():
                print("✅ Database schema initialized successfully")
                return 0
            else:
                print("❌ Database schema initialization failed")
                return 1
        
        # Show processing summary
        if args.summary:
            print("Processing Summary:")
            print("=" * 50)
            
            summary = processor.get_processing_summary()
            if summary:
                for item in summary:
                    print(f"Notice: {item['notice_id']}")
                    print(f"  File: {item['file_name']}")
                    print(f"  Pages: {item['page_count']}")
                    print(f"  Text Pages: {item['pages_with_text']}")
                    print(f"  Tables: {item['total_tables']}")
                    print(f"  Images: {item['total_images']}")
                    print(f"  Processed: {item['processed_at']}")
                    print(f"  File Size: {item['total_file_size']}")
                    print()
            else:
                print("No processing records found.")
            
            return 0
        
        # Search PDF content
        if args.search:
            print(f"Searching for: '{args.search}'")
            print("=" * 50)
            
            results = processor.search_pdf_content(args.search)
            if results:
                for result in results:
                    print(f"Notice: {result['notice_id']}")
                    print(f"  File: {result['file_name']}")
                    print(f"  Page: {result['page_number']}")
                    print(f"  Text: {result['text_content'][:200]}...")
                    print()
            else:
                print("No results found.")
            
            return 0
        
        # Extract structured content from existing PDFs
        if args.extract_structured:
            print("Extracting structured content from existing PDFs...")
            print("=" * 50)
            
            if not processor.test_connections():
                print("❌ Database connection failed")
                return 1
            
            stats = processor.process_structured_content_batch()
            
            print(f"Processed Documents: {stats['processed_docs']}")
            print(f"Failed Documents: {stats['failed_docs']}")
            print(f"Total Documents: {stats['total_docs']}")
            
            if stats['failed_docs'] == 0:
                print("✅ All documents processed successfully")
            else:
                print(f"⚠️ {stats['failed_docs']} documents failed processing")
            
            return 0
        
        # Show structured content summary
        if args.structured_summary:
            print("Structured Content Summary:")
            print("=" * 50)
            
            summary = processor.get_structured_content_summary()
            if summary:
                for item in summary:
                    print(f"Notice: {item['notice_id']}")
                    print(f"  File: {item['file_name']}")
                    print(f"  Status: {item['extraction_status']}")
                    print(f"  Document Title: {item['document_title'] or 'N/A'}")
                    print(f"  Asset Type: {item['asset_type'] or 'N/A'}")
                    print(f"  Asset Count: {item['asset_count'] or 0}")
                    print(f"  Bidding Type: {item['bidding_type'] or 'N/A'}")
                    print(f"  Trustee: {item['trustee_org'] or 'N/A'}")
                    print(f"  Missing Sections: {item['missing_sections_count'] or 0}")
                    print(f"  Processed: {item['processed_at']}")
                    print()
            else:
                print("No structured content found.")
            
            return 0
        
        # Search structured content
        if args.search_structured:
            print(f"Searching structured content for: '{args.search_structured}'")
            print("=" * 50)
            
            results = processor.search_structured_content(args.search_structured)
            if results:
                for result in results:
                    print(f"Notice: {result['notice_id']}")
                    print(f"  File: {result['file_name']}")
                    if 'section_data' in result:
                        print(f"  Section Data: {str(result['section_data'])[:200]}...")
                    else:
                        # Show relevant parts of structured content
                        content = result.get('structured_content', {})
                        if content:
                            sections = content.get('sections', {})
                            for section_name, section_data in sections.items():
                                if args.search_structured.lower() in str(section_data).lower():
                                    print(f"  Found in {section_name}: {str(section_data)[:200]}...")
                                    break
                    print()
            else:
                print("No results found in structured content.")
            
            return 0
        
        # Get assets by type
        if args.assets_by_type:
            print(f"Assets of type: '{args.assets_by_type}'")
            print("=" * 50)
            
            results = processor.get_assets_by_type(args.assets_by_type)
            if results:
                for result in results:
                    print(f"Notice: {result['notice_id']}")
                    print(f"  File: {result['file_name']}")
                    print(f"  Asset Type: {result['asset_type']}")
                    
                    asset_data = result.get('asset', {})
                    if asset_data:
                        print(f"  Registration No: {asset_data.get('registration_no', 'N/A')}")
                        print(f"  Title: {asset_data.get('title', 'N/A')}")
                        print(f"  Application Date: {asset_data.get('application_date', 'N/A')}")
                        print(f"  Registration Date: {asset_data.get('registration_date', 'N/A')}")
                        print(f"  Remark: {asset_data.get('remark', 'N/A')}")
                    print()
            else:
                print("No assets found of this type.")
            
            return 0
        
        # Process PDFs
        print("Starting PDF processing...")
        
        # Check if downloads directory exists
        if not os.path.exists(args.downloads_dir):
            print(f"❌ Downloads directory not found: {args.downloads_dir}")
            return 1
        
        # Initialize database if needed
        if not processor.test_connections():
            print("❌ Database connection failed")
            return 1
        
        if not processor.initialize_database():
            print("❌ Database initialization failed")
            return 1
        
        # Process specific notice or all PDFs
        if args.notice_id:
            print(f"Processing PDFs for notice ID: {args.notice_id}")
            stats = processor.process_specific_notice(args.notice_id)
        elif args.async_mode:
            print(f"Processing all PDFs asynchronously (max {args.concurrent} concurrent)")
            stats = asyncio.run(processor.process_all_pdfs_async(
                max_concurrent=args.concurrent,
                max_files=args.max_files
            ))
        else:
            print("Processing all PDFs synchronously")
            stats = processor.process_all_pdfs(max_files=args.max_files)
        
        # Print results
        print("\nProcessing Results:")
        print("=" * 50)
        
        if args.notice_id:
            print(f"Notice ID: {stats['notice_id']}")
            print(f"Processed Files: {stats['processed_files']}")
            print(f"Failed Files: {stats['failed_files']}")
            
            for file_info in stats['files']:
                status = "✅" if file_info['success'] else "❌"
                print(f"  {status} {file_info['file_name']}")
        else:
            print(f"Total Processed Files: {stats['processed_files']}")
            print(f"Total Failed Files: {stats['failed_files']}")
            print(f"Total Text Blocks: {stats['total_text_blocks']}")
            print(f"Total Tables: {stats['total_tables']}")
            print(f"Total Images: {stats['total_images']}")
        
        # Show final status
        if stats['failed_files'] == 0:
            print("✅ All files processed successfully")
            return 0
        else:
            print(f"⚠️ {stats['failed_files']} files failed processing")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Processing interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        print(f"❌ PDF processing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())