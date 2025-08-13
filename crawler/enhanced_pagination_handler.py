"""
Enhanced pagination handler with attachment download capabilities
"""
import asyncio
from typing import Optional, List, Dict, Any
from crawler.browser_controller import BrowserController
from crawler.data_extractor import DataExtractor
from crawler.detail_extractor import DetailExtractor
from crawler.attachment_downloader import AttachmentDownloader
from utils.logger import setup_logger
from config import MAX_RETRIES, RETRY_DELAY, DOWNLOAD_ATTACHMENTS


class EnhancedPaginationHandler:
    """Enhanced pagination handler that processes details and downloads attachments"""
    
    def __init__(self, 
                 browser_controller: BrowserController, 
                 data_extractor: DataExtractor,
                 detail_extractor: DetailExtractor,
                 attachment_downloader: Optional[AttachmentDownloader] = None):
        self.browser = browser_controller
        self.extractor = data_extractor
        self.detail_extractor = detail_extractor
        self.attachment_downloader = attachment_downloader
        self.logger = setup_logger(__name__)
        
    async def crawl_all_pages_with_details(self, 
                                         start_page: int = 1, 
                                         max_pages: Optional[int] = None,
                                         download_attachments: bool = True) -> Dict[str, Any]:
        """Crawl all pages with detailed information and attachment downloads"""
        
        all_data = []
        all_attachments = []
        current_page = start_page
        consecutive_empty_pages = 0
        max_consecutive_empty = 3
        
        self.logger.info(f"Starting enhanced crawl from page {start_page}")
        if download_attachments and self.attachment_downloader:
            self.logger.info("Attachment downloading is enabled")
        
        while True:
            # Check if we've reached max pages limit
            if max_pages and current_page > start_page + max_pages - 1:
                self.logger.info(f"Reached maximum pages limit ({max_pages})")
                break
                
            # Crawl single page with details
            page_result = await self._crawl_single_page_with_details(
                current_page, 
                download_attachments
            )
            
            if page_result is None:
                self.logger.error(f"Failed to load page {current_page}")
                consecutive_empty_pages += 1
            elif len(page_result['notices']) == 0:
                self.logger.info(f"No data found on page {current_page}")
                consecutive_empty_pages += 1
            else:
                self.logger.info(f"Processed {len(page_result['notices'])} notices on page {current_page}")
                all_data.extend(page_result['notices'])
                if page_result['attachments']:
                    all_attachments.extend(page_result['attachments'])
                consecutive_empty_pages = 0
                
            # Check if we should stop
            if consecutive_empty_pages >= max_consecutive_empty:
                self.logger.info(f"Stopping: {consecutive_empty_pages} consecutive empty pages")
                break
                
            current_page += 1
            await asyncio.sleep(1)  # Respectful delay
            
        # Generate summary
        summary = {
            'total_notices': len(all_data),
            'total_pages_crawled': current_page - start_page,
            'notices_with_attachments': len([n for n in all_data if n.get('attachment_count', 0) > 0]),
            'total_attachments_downloaded': len(all_attachments),
            'attachment_download_enabled': download_attachments and self.attachment_downloader is not None
        }
        
        if self.attachment_downloader and all_attachments:
            attachment_summary = self.attachment_downloader.get_download_summary(all_attachments)
            summary.update(attachment_summary)
        
        self.logger.info(f"Enhanced crawling completed: {summary}")
        
        return {
            'notices': all_data,
            'attachments': all_attachments,
            'summary': summary
        }
        
    async def _crawl_single_page_with_details(self, 
                                            page_num: int,
                                            download_attachments: bool = True) -> Optional[Dict[str, Any]]:
        """Crawl a single page with detailed processing"""
        
        for attempt in range(MAX_RETRIES):
            try:
                self.logger.debug(f"Processing page {page_num} (attempt {attempt + 1})")
                
                # Navigate to the page
                success = await self.browser.navigate_to_page(page_num)
                if not success:
                    self.logger.warning(f"Failed to navigate to page {page_num} on attempt {attempt + 1}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return None
                    
                # Check if page has data
                has_data = await self.browser.has_data()
                if not has_data:
                    self.logger.info(f"Page {page_num} has no data")
                    return {'notices': [], 'attachments': []}
                    
                # Get page content and extract basic notice data
                content = await self.browser.get_page_content()
                if not content:
                    self.logger.warning(f"Empty content received for page {page_num}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return {'notices': [], 'attachments': []}
                    
                # Extract basic notice data
                notices = self.extractor.extract_auction_data(content, page_num)
                if not notices:
                    return {'notices': [], 'attachments': []}
                
                # Process each notice for detailed information
                processed_notices = []
                all_attachments = []
                
                for notice in notices:
                    try:
                        # Process detail page if links are available
                        detail_result = await self._process_notice_details(
                            notice, 
                            download_attachments
                        )
                        
                        if detail_result:
                            processed_notices.append(detail_result['notice'])
                            if detail_result['attachments']:
                                all_attachments.append(detail_result['attachments'])
                        else:
                            # Add basic notice even if detail processing failed
                            notice['detail_processing_failed'] = True
                            processed_notices.append(notice)
                            
                    except Exception as e:
                        self.logger.error(f"Error processing notice {notice.get('sequence_number', 'unknown')}: {e}")
                        notice['detail_processing_error'] = str(e)
                        processed_notices.append(notice)
                        
                return {
                    'notices': processed_notices,
                    'attachments': all_attachments
                }
                
            except Exception as e:
                self.logger.error(f"Error crawling page {page_num} on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return None
                
        self.logger.error(f"Failed to crawl page {page_num} after {MAX_RETRIES} attempts")
        return None
        
    async def _process_notice_details(self, 
                                    notice: Dict[str, Any],
                                    download_attachments: bool = True) -> Optional[Dict[str, Any]]:
        """Process detailed information for a single notice"""
        
        try:
            # Extract the detail page link
            links = notice.get('links', [])
            if not links:
                self.logger.warning(f"No detail links found for notice {notice.get('sequence_number', 'unknown')}")
                return None
                
            detail_href = links[0].get('href', '')
            if not detail_href:
                self.logger.warning(f"Empty detail link for notice {notice.get('sequence_number', 'unknown')}")
                return None
                
            # Navigate to detail page
            detail_success = await self.browser.navigate_to_detail_page(detail_href)
            if not detail_success:
                self.logger.warning(f"Failed to navigate to detail page for notice {notice.get('sequence_number', 'unknown')}")
                return None
                
            # Get detail page content
            detail_content = await self.browser.get_page_content()
            if not detail_content:
                self.logger.warning(f"Empty detail content for notice {notice.get('sequence_number', 'unknown')}")
                await self.browser.go_back_to_list()
                return None
                
            # Extract detailed information
            detail_data = self.detail_extractor.extract_detail_data(detail_content, notice)
            
            # Combine basic and detailed data
            enhanced_notice = {**notice, **detail_data}
            enhanced_notice['detail_url'] = await self.browser.get_current_url()
            
            # Download attachments if enabled
            attachments_info = None
            if download_attachments and self.attachment_downloader:
                try:
                    attachments_info = await self.attachment_downloader.download_notice_attachments(
                        self.browser.page, enhanced_notice
                    )
                    
                    enhanced_notice['attachment_count'] = len(attachments_info.get('attachments', []))
                    enhanced_notice['attachment_download_errors'] = len(attachments_info.get('download_errors', []))
                    enhanced_notice['attachments_dir'] = attachments_info.get('notice_dir', '')
                    
                except Exception as e:
                    self.logger.error(f"Error downloading attachments for notice {notice.get('sequence_number', 'unknown')}: {e}")
                    enhanced_notice['attachment_download_error'] = str(e)
                    enhanced_notice['attachment_count'] = 0
            else:
                enhanced_notice['attachment_count'] = 0
                
            # Go back to list page
            await self.browser.go_back_to_list()
            
            return {
                'notice': enhanced_notice,
                'attachments': attachments_info
            }
            
        except Exception as e:
            self.logger.error(f"Error processing notice details: {e}")
            # Try to go back to list page
            try:
                await self.browser.go_back_to_list()
            except:
                pass
            return None