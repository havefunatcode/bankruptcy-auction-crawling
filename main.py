"""
Main crawler application for bankruptcy auction data collection
"""
import asyncio
import argparse
import sys
from datetime import datetime
from crawler.browser_controller import BrowserController
from crawler.data_extractor import DataExtractor
from crawler.detail_extractor import DetailExtractor
from crawler.pagination_handler import PaginationHandler
from crawler.enhanced_pagination_handler import EnhancedPaginationHandler
from crawler.data_storage import DataStorage
from crawler.attachment_downloader import AttachmentDownloader
from utils.logger import setup_logger
from utils.error_handler import error_handler, RateLimiter
from config import BASE_URL, DELAY_BETWEEN_REQUESTS, DOWNLOAD_ATTACHMENTS, DOWNLOADS_DIR


class BankruptcyAuctionCrawler:
    """Main crawler application"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.browser = None
        self.extractor = DataExtractor()
        self.detail_extractor = DetailExtractor()
        self.storage = DataStorage()
        self.attachment_downloader = AttachmentDownloader(DOWNLOADS_DIR) if DOWNLOAD_ATTACHMENTS else None
        self.rate_limiter = RateLimiter(1.0 / DELAY_BETWEEN_REQUESTS)
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.browser = BrowserController()
        await self.browser.start()
        self.pagination_handler = PaginationHandler(self.browser, self.extractor)
        self.enhanced_pagination_handler = EnhancedPaginationHandler(
            self.browser, 
            self.extractor, 
            self.detail_extractor,
            self.attachment_downloader
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
            
    async def crawl(self, 
                   start_page: int = 1, 
                   max_pages: int = None,
                   preview_mode: bool = False) -> dict:
        """Main crawling function"""
        
        start_time = datetime.now()
        self.logger.info(f"Starting bankruptcy auction crawl from page {start_page}")
        
        try:
            # Navigate to base URL
            success = await self.browser.navigate_to_url(BASE_URL)
            if not success:
                raise Exception("Failed to navigate to base URL")
                
            # Preview mode - just check first few pages
            if preview_mode:
                return await self._preview_crawl(start_page)
                
            # Full crawl
            all_data = await self.pagination_handler.crawl_all_pages(
                start_page=start_page,
                max_pages=max_pages
            )
            
            # Save data
            saved_files = {}
            if all_data:
                saved_files = self.storage.save_data(all_data, f"pages_{start_page}+")
                
            # Calculate statistics
            end_time = datetime.now()
            duration = end_time - start_time
            
            results = {
                'success': True,
                'total_items': len(all_data),
                'start_page': start_page,
                'max_pages': max_pages,
                'duration_seconds': duration.total_seconds(),
                'items_per_second': len(all_data) / duration.total_seconds() if duration.total_seconds() > 0 else 0,
                'saved_files': saved_files,
                'error_statistics': error_handler.get_error_statistics()
            }
            
            self.logger.info(f"Crawl completed successfully: {len(all_data)} items in {duration}")
            return results
            
        except Exception as e:
            self.logger.error(f"Crawl failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_statistics': error_handler.get_error_statistics()
            }
            
    async def _preview_crawl(self, start_page: int) -> dict:
        """Preview crawl to check data availability"""
        
        self.logger.info("Running preview mode...")
        
        # Get page range info
        page_info = await self.pagination_handler.get_page_range_info(
            start_page=start_page,
            sample_pages=3
        )
        
        # Try to find last page
        estimated_last_page = await self.pagination_handler.find_last_page(
            start_page=start_page,
            max_search=20
        )
        
        return {
            'success': True,
            'preview_mode': True,
            'page_info': page_info,
            'estimated_last_page': estimated_last_page,
            'estimated_total_items': page_info.get('avg_items_per_page', 0) * estimated_last_page
        }
        
    async def crawl_specific_pages(self, page_numbers: list) -> dict:
        """Crawl specific page numbers"""
        
        self.logger.info(f"Crawling specific pages: {page_numbers}")
        
        try:
            # Navigate to base URL
            success = await self.browser.navigate_to_url(BASE_URL)
            if not success:
                raise Exception("Failed to navigate to base URL")
                
            all_data = []
            failed_pages = []
            
            for page_num in page_numbers:
                try:
                    await self.rate_limiter.acquire()
                    
                    page_data = await self.pagination_handler._crawl_single_page(page_num)
                    if page_data is not None:
                        all_data.extend(page_data)
                        self.logger.info(f"Successfully crawled page {page_num}: {len(page_data)} items")
                    else:
                        failed_pages.append(page_num)
                        
                except Exception as e:
                    self.logger.error(f"Failed to crawl page {page_num}: {e}")
                    failed_pages.append(page_num)
                    
            # Save data
            saved_files = {}
            if all_data:
                page_range = f"{min(page_numbers)}-{max(page_numbers)}"
                saved_files = self.storage.save_data(all_data, f"pages_{page_range}")
                
            return {
                'success': True,
                'total_items': len(all_data),
                'pages_requested': page_numbers,
                'pages_failed': failed_pages,
                'saved_files': saved_files
            }
            
        except Exception as e:
            self.logger.error(f"Specific page crawl failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
            
    async def crawl_with_attachments(self, 
                                   start_page: int = 1, 
                                   max_pages: int = None,
                                   download_attachments: bool = True) -> dict:
        """Enhanced crawling with detail page processing and attachment downloads"""
        
        start_time = datetime.now()
        self.logger.info(f"Starting enhanced crawl with attachments from page {start_page}")
        
        try:
            # Navigate to base URL
            success = await self.browser.navigate_to_url(BASE_URL)
            if not success:
                raise Exception("Failed to navigate to base URL")
                
            # Enhanced crawl with details and attachments
            crawl_result = await self.enhanced_pagination_handler.crawl_all_pages_with_details(
                start_page=start_page,
                max_pages=max_pages,
                download_attachments=download_attachments
            )
            
            all_data = crawl_result['notices']
            all_attachments = crawl_result['attachments']
            crawl_summary = crawl_result['summary']
            
            # Save data
            saved_files = {}
            if all_data:
                saved_files = self.storage.save_data(all_data, f"enhanced_pages_{start_page}+")
                
            # Save attachment summary
            if all_attachments and self.attachment_downloader:
                attachment_summary = self.attachment_downloader.get_download_summary(all_attachments)
                
                # Save attachment summary to file
                import json
                import os
                summary_file = os.path.join(self.storage.output_dir, f"attachment_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump(attachment_summary, f, ensure_ascii=False, indent=2)
                saved_files['attachment_summary'] = summary_file
                
            # Calculate statistics
            end_time = datetime.now()
            duration = end_time - start_time
            
            results = {
                'success': True,
                'mode': 'enhanced_with_attachments',
                'total_notices': len(all_data),
                'start_page': start_page,
                'max_pages': max_pages,
                'duration_seconds': duration.total_seconds(),
                'notices_per_second': len(all_data) / duration.total_seconds() if duration.total_seconds() > 0 else 0,
                'crawl_summary': crawl_summary,
                'saved_files': saved_files,
                'error_statistics': error_handler.get_error_statistics()
            }
            
            self.logger.info(f"Enhanced crawl completed: {len(all_data)} notices in {duration}")
            if download_attachments:
                self.logger.info(f"Downloaded attachments for {crawl_summary.get('notices_with_attachments', 0)} notices")
                
            return results
            
        except Exception as e:
            self.logger.error(f"Enhanced crawl failed: {e}")
            return {
                'success': False,
                'mode': 'enhanced_with_attachments',
                'error': str(e),
                'error_statistics': error_handler.get_error_statistics()
            }


async def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='Bankruptcy Auction Crawler')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to crawl')
    parser.add_argument('--preview', action='store_true', help='Preview mode - check data availability')
    parser.add_argument('--pages', nargs='+', type=int, help='Specific page numbers to crawl')
    parser.add_argument('--headless', action='store_false', default=True, help='Run browser in visible mode (default: headless)')
    parser.add_argument('--with-attachments', action='store_true', help='Download attachments from detail pages')
    parser.add_argument('--no-attachments', action='store_true', help='Disable attachment downloads (faster crawling)')
    
    args = parser.parse_args()
    
    # Update config based on arguments
    if not args.headless:
        import config
        config.HEADLESS = False
        
    # Determine attachment download mode
    download_attachments = DOWNLOAD_ATTACHMENTS  # Default from config
    if args.with_attachments:
        download_attachments = True
    elif args.no_attachments:
        download_attachments = False
        
    try:
        async with BankruptcyAuctionCrawler() as crawler:
            if args.pages:
                # Crawl specific pages
                result = await crawler.crawl_specific_pages(args.pages)
            elif download_attachments:
                # Enhanced crawl with attachments
                result = await crawler.crawl_with_attachments(
                    start_page=args.start_page,
                    max_pages=args.max_pages,
                    download_attachments=download_attachments
                )
            else:
                # Regular crawl
                result = await crawler.crawl(
                    start_page=args.start_page,
                    max_pages=args.max_pages,
                    preview_mode=args.preview
                )
                
            # Print results
            print("\n" + "="*60)
            print("CRAWL RESULTS")
            print("="*60)
            
            if result['success']:
                if args.preview:
                    print(f"Preview Mode Results:")
                    print(f"  Estimated Last Page: {result.get('estimated_last_page', 'Unknown')}")
                    print(f"  Estimated Total Items: {result.get('estimated_total_items', 'Unknown')}")
                    
                    page_info = result.get('page_info', {})
                    if page_info.get('sampled_pages'):
                        print(f"  Sample Pages:")
                        for page in page_info['sampled_pages']:
                            status = "✓" if page['has_data'] else "✗"
                            print(f"    Page {page['page_number']}: {status} ({page['item_count']} items)")
                elif result.get('mode') == 'enhanced_with_attachments':
                    # Enhanced mode results
                    print(f"Enhanced Crawl Results:")
                    print(f"Total Notices Crawled: {result.get('total_notices', 0)}")
                    print(f"Duration: {result.get('duration_seconds', 0):.1f} seconds")
                    print(f"Rate: {result.get('notices_per_second', 0):.2f} notices/second")
                    
                    crawl_summary = result.get('crawl_summary', {})
                    if crawl_summary:
                        print(f"Notices with Attachments: {crawl_summary.get('notices_with_attachments', 0)}")
                        print(f"Total Attachments Downloaded: {crawl_summary.get('total_attachments_downloaded', 0)}")
                        if crawl_summary.get('total_size_mb'):
                            print(f"Total Downloaded Size: {crawl_summary.get('total_size_mb', 0):.2f} MB")
                    
                    saved_files = result.get('saved_files', {})
                    if saved_files:
                        print(f"Saved Files:")
                        for file_type, file_path in saved_files.items():
                            print(f"  {file_type.upper()}: {file_path}")
                else:
                    # Regular mode results
                    print(f"Total Items Crawled: {result.get('total_items', 0)}")
                    print(f"Duration: {result.get('duration_seconds', 0):.1f} seconds")
                    print(f"Rate: {result.get('items_per_second', 0):.2f} items/second")
                    
                    saved_files = result.get('saved_files', {})
                    if saved_files:
                        print(f"Saved Files:")
                        for file_type, file_path in saved_files.items():
                            print(f"  {file_type.upper()}: {file_path}")
                            
                    failed_pages = result.get('pages_failed', [])
                    if failed_pages:
                        print(f"Failed Pages: {failed_pages}")
                        
            else:
                print(f"Crawl failed: {result.get('error', 'Unknown error')}")
                
            # Print error statistics if any
            error_stats = result.get('error_statistics', {})
            if error_stats.get('total_errors', 0) > 0:
                print(f"\nError Statistics:")
                print(f"  Total Errors: {error_stats['total_errors']}")
                for func, count in error_stats.get('error_counts', {}).items():
                    print(f"  {func}: {count} errors")
                    
            print("="*60)
            
    except KeyboardInterrupt:
        print("\nCrawl interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())