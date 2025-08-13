"""
Pagination handler for managing page navigation and end-of-data detection
"""
import asyncio
from typing import Optional, List, Dict, Any
from crawler.browser_controller import BrowserController
from crawler.data_extractor import DataExtractor
from utils.logger import setup_logger
from config import MAX_RETRIES, RETRY_DELAY


class PaginationHandler:
    """Handles pagination logic and data collection across pages"""
    
    def __init__(self, browser_controller: BrowserController, data_extractor: DataExtractor):
        self.browser = browser_controller
        self.extractor = data_extractor
        self.logger = setup_logger(__name__)
        
    async def crawl_all_pages(self, start_page: int = 1, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """Crawl all pages starting from start_page until no more data"""
        all_data = []
        current_page = start_page
        consecutive_empty_pages = 0
        max_consecutive_empty = 3  # Stop after 3 consecutive empty pages
        
        self.logger.info(f"Starting to crawl from page {start_page}")
        
        while True:
            # Check if we've reached max pages limit
            if max_pages and current_page > start_page + max_pages - 1:
                self.logger.info(f"Reached maximum pages limit ({max_pages})")
                break
                
            # Attempt to navigate to current page
            page_data = await self._crawl_single_page(current_page)
            
            if page_data is None:
                # Failed to load page
                self.logger.error(f"Failed to load page {current_page}")
                consecutive_empty_pages += 1
            elif len(page_data) == 0:
                # Page loaded but no data found
                self.logger.info(f"No data found on page {current_page}")
                consecutive_empty_pages += 1
            else:
                # Found data
                self.logger.info(f"Found {len(page_data)} items on page {current_page}")
                all_data.extend(page_data)
                consecutive_empty_pages = 0
                
            # Check if we should stop (too many consecutive empty pages)
            if consecutive_empty_pages >= max_consecutive_empty:
                self.logger.info(f"Stopping crawl: {consecutive_empty_pages} consecutive empty pages")
                break
                
            # Move to next page
            current_page += 1
            
            # Add a small delay to be respectful
            await asyncio.sleep(1)
            
        self.logger.info(f"Crawling completed. Total items collected: {len(all_data)}")
        return all_data
        
    async def _crawl_single_page(self, page_num: int) -> Optional[List[Dict[str, Any]]]:
        """Crawl a single page with retry logic"""
        
        for attempt in range(MAX_RETRIES):
            try:
                self.logger.debug(f"Attempting to crawl page {page_num} (attempt {attempt + 1})")
                
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
                    return []
                    
                # Get page content and extract data
                content = await self.browser.get_page_content()
                if not content:
                    self.logger.warning(f"Empty content received for page {page_num}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return []
                    
                # Extract auction data
                page_data = self.extractor.extract_auction_data(content, page_num)
                return page_data
                
            except Exception as e:
                self.logger.error(f"Error crawling page {page_num} on attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return None
                
        self.logger.error(f"Failed to crawl page {page_num} after {MAX_RETRIES} attempts")
        return None
        
    async def find_last_page(self, start_page: int = 1, max_search: int = 100) -> int:
        """Find the last page with data using binary search approach"""
        
        self.logger.info("Attempting to find last page with data")
        
        # First, do a rough estimation by checking every 10 pages
        last_known_page_with_data = start_page
        search_page = start_page
        
        while search_page <= max_search:
            try:
                success = await self.browser.navigate_to_page(search_page)
                if success:
                    has_data = await self.browser.has_data()
                    if has_data:
                        last_known_page_with_data = search_page
                        search_page += 10  # Jump by 10
                    else:
                        break
                else:
                    break
                    
            except Exception as e:
                self.logger.error(f"Error while searching for last page at page {search_page}: {e}")
                break
                
        # Now do a more precise search between last_known_page_with_data and search_page
        if search_page > last_known_page_with_data + 1:
            for page in range(last_known_page_with_data + 1, min(search_page + 1, max_search + 1)):
                try:
                    success = await self.browser.navigate_to_page(page)
                    if success:
                        has_data = await self.browser.has_data()
                        if has_data:
                            last_known_page_with_data = page
                        else:
                            break
                    else:
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error while fine-searching at page {page}: {e}")
                    break
                    
        self.logger.info(f"Last page with data appears to be: {last_known_page_with_data}")
        return last_known_page_with_data
        
    async def get_page_range_info(self, start_page: int = 1, sample_pages: int = 5) -> Dict[str, Any]:
        """Get information about page range and data availability"""
        
        info = {
            'start_page': start_page,
            'sampled_pages': [],
            'estimated_last_page': None,
            'total_estimated_items': 0
        }
        
        # Sample a few pages to get an idea of data availability
        for page_num in range(start_page, start_page + sample_pages):
            try:
                success = await self.browser.navigate_to_page(page_num)
                if success:
                    has_data = await self.browser.has_data()
                    if has_data:
                        content = await self.browser.get_page_content()
                        page_data = self.extractor.extract_auction_data(content, page_num)
                        
                        info['sampled_pages'].append({
                            'page_number': page_num,
                            'has_data': True,
                            'item_count': len(page_data)
                        })
                    else:
                        info['sampled_pages'].append({
                            'page_number': page_num,
                            'has_data': False,
                            'item_count': 0
                        })
                        break  # Stop sampling if we hit an empty page
                else:
                    break
                    
            except Exception as e:
                self.logger.error(f"Error sampling page {page_num}: {e}")
                break
                
        # Calculate estimates
        pages_with_data = [p for p in info['sampled_pages'] if p['has_data']]
        if pages_with_data:
            avg_items_per_page = sum(p['item_count'] for p in pages_with_data) / len(pages_with_data)
            info['avg_items_per_page'] = avg_items_per_page
            
        return info