"""
Browser controller for managing Playwright browser sessions
"""
import asyncio
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from utils.logger import setup_logger
from config import HEADLESS, BROWSER_TYPE, PAGE_LOAD_TIMEOUT, DELAY_BETWEEN_REQUESTS


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
            
            # For page 1, just reload the page
            if page_num == 1:
                await self.page.reload(wait_until='networkidle')
                await self.delay()
                return True
            
            # Look for pagination links - this site uses JavaScript function calls
            # Check if page link exists
            page_link = await self.page.query_selector(f'a[onclick*="fn_egov_select_brdMstr({page_num})"]')
            if page_link:
                await page_link.click()
                await self.page.wait_for_load_state('networkidle')
                await self.delay()
                return True
            else:
                # Try to navigate using form submission
                form_script = f"""
                document.frm.pageIndex.value = '{page_num}';
                document.frm.submit();
                """
                await self.page.evaluate(form_script)
                await self.page.wait_for_load_state('networkidle')
                await self.delay()
                return True
                    
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
            self.logger.info(f"Navigating to detail page")
            
            # Find the link with matching href
            link_selector = f'a[href="{notice_link_href}"]'
            detail_link = await self.page.query_selector(link_selector)
            
            if detail_link:
                # Get link text for logging
                link_text = await detail_link.text_content()
                self.logger.info(f"Clicking detail link: '{link_text.strip()}'")
                
                # Click the link
                await detail_link.click()
                await self.page.wait_for_load_state('networkidle')
                await self.delay()
                return True
            else:
                self.logger.warning(f"Detail link not found: {notice_link_href}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to navigate to detail page: {e}")
            return False
            
    async def go_back_to_list(self) -> bool:
        """Go back to the list page"""
        try:
            self.logger.info("Going back to list page")
            await self.page.go_back()
            await self.page.wait_for_load_state('networkidle')
            await self.delay()
            return True
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