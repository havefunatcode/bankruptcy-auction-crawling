"""
Browser controller for managing Playwright browser sessions
"""
import asyncio
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from utils.logger import setup_logger
from config import HEADLESS, BROWSER_TYPE, PAGE_LOAD_TIMEOUT, DELAY_BETWEEN_REQUESTS, BASE_URL


class BrowserController:
    """Manages browser sessions and page navigation"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def start(self):
        """Initialize browser and create context"""
        try:
            self.logger.info("Starting browser...")
            self.playwright = await async_playwright().start()
            
            # Get browser based on configuration
            browser_launcher = getattr(self.playwright, BROWSER_TYPE)
            self.browser = await browser_launcher.launch(headless=HEADLESS)
            
            # Create context with Korean locale
            self.context = await self.browser.new_context(
                locale='ko-KR',
                timezone_id='Asia/Seoul'
            )
            
            # Create page
            self.page = await self.context.new_page()
            self.page.set_default_timeout(PAGE_LOAD_TIMEOUT)
            
            self.logger.info("Browser started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start browser: {e}")
            await self.close()
            raise
            
    async def navigate_to_url(self, url: str) -> bool:
        """Navigate to specific URL"""
        try:
            self.logger.info(f"Navigating to: {url}")
            await self.page.goto(url, wait_until='networkidle')
            await self.delay()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            return False
            
    async def navigate_to_page(self, page_num: int) -> bool:
        """Navigate to specific page number"""
        try:
            self.logger.info(f"Navigating to page {page_num}")
            
            # For page 1, ensure we're on the main list page
            if page_num == 1:
                await self.navigate_to_url(BASE_URL)
                return True
            
            # First ensure we're on the main list page
            current_url = await self.get_current_url()
            if 'RealNoticeList.work' not in current_url:
                await self.navigate_to_url(BASE_URL)
                await asyncio.sleep(2)  # Give more time for page to stabilize
            
            # Wait for page to fully load and stabilize
            await asyncio.sleep(1)
            
            # Look for pagination links - this site uses JavaScript function calls
            # Check if page link exists
            page_link = await self.page.query_selector(f'a[onclick*="fn_egov_select_brdMstr({page_num})"]')
            if page_link:
                await page_link.click()
                await self.page.wait_for_load_state('networkidle')
                await self.delay()
                return True
            else:
                # Try to navigate using form submission with better error handling
                form_check_script = """
                try {
                    if (typeof document !== 'undefined' && 
                        typeof document.frm !== 'undefined' && 
                        document.frm && 
                        typeof document.frm.pageIndex !== 'undefined' &&
                        document.frm.pageIndex) {
                        return true;
                    } else {
                        return false;
                    }
                } catch (e) {
                    return false;
                }
                """
                
                # Wait a bit more and try multiple times
                for attempt in range(3):
                    form_exists = await self.page.evaluate(form_check_script)
                    if form_exists:
                        break
                    self.logger.debug(f"Form not ready on attempt {attempt + 1}, waiting...")
                    await asyncio.sleep(1)
                
                if form_exists:
                    form_script = f"""
                    try {{
                        document.frm.pageIndex.value = '{page_num}';
                        document.frm.submit();
                        return true;
                    }} catch (e) {{
                        console.error('Form submission error:', e);
                        return false;
                    }}
                    """
                    result = await self.page.evaluate(form_script)
                    if result:
                        await self.page.wait_for_load_state('networkidle')
                        await self.delay()
                        return True
                    else:
                        self.logger.warning(f"Form submission failed for page {page_num}")
                        return False
                else:
                    self.logger.warning(f"Form not found for page navigation to page {page_num}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to navigate to page {page_num}: {e}")
            return False
            
    async def get_page_content(self) -> str:
        """Get current page HTML content"""
        try:
            return await self.page.content()
        except Exception as e:
            self.logger.error(f"Failed to get page content: {e}")
            return ""
            
    async def has_data(self) -> bool:
        """Check if current page has auction data"""
        try:
            # Look for the "검색 결과가 없습니다" message
            no_data_message = await self.page.query_selector('text=검색 결과가 없습니다')
            if no_data_message:
                return False
                
            # Check if there are any data rows in the table (use correct selector)
            data_rows = await self.page.query_selector_all('table.tableHor tbody tr')
            
            # Filter out header rows and "no data" rows
            valid_rows = []
            for row in data_rows:
                text_content = await row.text_content()
                if text_content and "검색 결과가 없습니다" not in text_content and text_content.strip():
                    valid_rows.append(row)
                    
            self.logger.debug(f"Found {len(valid_rows)} valid data rows")
            return len(valid_rows) > 0
            
        except Exception as e:
            self.logger.error(f"Failed to check for data: {e}")
            return False
            
    async def delay(self):
        """Add delay between requests"""
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
        
    async def close(self):
        """Close browser and cleanup resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
                
            self.logger.info("Browser closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing browser: {e}")
            
    async def get_current_page_number(self) -> int:
        """Get current page number from the page"""
        try:
            page_input = await self.page.query_selector('input[name="nowpage"]')
            if page_input:
                value = await page_input.get_attribute('value')
                return int(value) if value else 1
            return 1
        except Exception as e:
            self.logger.error(f"Failed to get current page number: {e}")
            return 1
            
    async def navigate_to_detail_page(self, notice_link_href: str) -> bool:
        """Navigate to a specific notice detail page"""
        try:
            self.logger.info(f"Navigating to detail page: {notice_link_href}")
            
            # Wait for page to stabilize
            await asyncio.sleep(1)
            
            # Verify we're on the list page
            current_url = await self.get_current_url()
            if 'RealNoticeView' in current_url:
                # We're already on a detail page, go back first
                await self.go_back_to_list()
                await asyncio.sleep(1)
            
            # Extract seq_id from the href for better matching
            seq_id = None
            if 'seq_id=' in notice_link_href:
                seq_id = notice_link_href.split('seq_id=')[1].split('&')[0]
                self.logger.debug(f"Extracted seq_id: {seq_id}")
            
            # Try multiple selector strategies with more specific patterns
            selectors = [
                f'a[href="{notice_link_href}"]',  # Exact match
                f'a[href*="seq_id={seq_id}"]' if seq_id else None,  # Match by seq_id
                f'a[href*="{seq_id}"]' if seq_id else None,  # Partial seq_id match
            ]
            
            # Remove None selectors
            selectors = [s for s in selectors if s]
            
            detail_link = None
            for i, selector in enumerate(selectors):
                self.logger.debug(f"Trying selector {i+1}: {selector}")
                detail_link = await self.page.query_selector(selector)
                if detail_link:
                    self.logger.debug(f"Found link with selector {i+1}")
                    break
            
            if detail_link:
                # Get link text for logging
                link_text = await detail_link.text_content()
                self.logger.info(f"Clicking detail link: '{link_text.strip()}'")
                
                # Verify the link is visible and clickable
                is_visible = await detail_link.is_visible()
                if not is_visible:
                    self.logger.warning("Link is not visible, scrolling to it")
                    await detail_link.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                
                # Try clicking the link (first attempt - single click)
                await detail_link.click()
                await asyncio.sleep(1)
                
                # Check if single click worked
                new_url = await self.get_current_url()
                if 'RealNoticeView' in new_url:
                    self.logger.info("Successfully navigated to detail page (single click)")
                    await self.delay()
                    return True
                
                # If single click didn't work, try double click
                self.logger.debug("Single click failed, trying double click")
                await detail_link.dblclick()
                await self.page.wait_for_load_state('networkidle')
                await self.delay()
                
                # Verify we actually navigated to the detail page
                final_url = await self.get_current_url()
                if 'RealNoticeView' in final_url:
                    self.logger.info("Successfully navigated to detail page (double click)")
                    return True
                else:
                    self.logger.warning(f"Both click attempts failed, still on list page: {final_url}")
                    return False
                    
            else:
                self.logger.warning(f"Detail link not found with any selector: {notice_link_href}")
                # Debug: Log all available detail links
                all_links = await self.page.query_selector_all('a[href*="RealNoticeView"]')
                self.logger.debug(f"Found {len(all_links)} total detail links on page")
                
                if seq_id:
                    # Try to find any link containing the seq_id in text or nearby elements
                    seq_links = await self.page.query_selector_all(f'a:has-text("{seq_id}")')
                    self.logger.debug(f"Found {len(seq_links)} links containing seq_id in text")
                
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to navigate to detail page: {e}")
            return False
            
    async def go_back_to_list(self) -> bool:
        """Go back to the list page"""
        try:
            self.logger.info("Going back to list page")
            
            # Try going back first
            try:
                await self.page.go_back()
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                await self.delay()
            except Exception as back_error:
                self.logger.warning(f"Failed to go back, trying direct navigation: {back_error}")
                # Fallback: Navigate directly to the list page
                current_url = await self.get_current_url()
                if 'RealNoticeView' in current_url:
                    # Extract page info from current URL and navigate back to list
                    await self.navigate_to_url(BASE_URL)
                    await asyncio.sleep(2)
            
            # Wait for JavaScript and page state to stabilize
            await asyncio.sleep(1)
            
            # Verify we're back on the list page and page elements are loaded
            for attempt in range(3):
                try:
                    # Check if the main table is loaded
                    table = await self.page.query_selector('table.tableHor')
                    if table:
                        self.logger.debug("Successfully returned to list page")
                        return True
                    else:
                        self.logger.debug(f"Table not found on attempt {attempt + 1}, waiting...")
                        await asyncio.sleep(1)
                except Exception as e:
                    self.logger.debug(f"Error checking table on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(1)
            
            self.logger.warning("Returned to list page but table verification failed")
            return True  # Still return True as we went back successfully
            
        except Exception as e:
            self.logger.error(f"Failed to go back to list page: {e}")
            return False
            
    async def get_current_url(self) -> str:
        """Get current page URL"""
        try:
            return self.page.url
        except Exception as e:
            self.logger.error(f"Failed to get current URL: {e}")
            return ""