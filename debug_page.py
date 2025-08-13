"""
Debug script to inspect the website structure
"""
import asyncio
from playwright.async_api import async_playwright


async def debug_page():
    """Debug the page structure"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='ko-KR')
        page = await context.new_page()
        
        print("Navigating to the page...")
        await page.goto("https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work")
        
        # Wait for page to load
        await page.wait_for_load_state('networkidle')
        
        # Take a screenshot
        await page.screenshot(path="debug_screenshot.png")
        print("Screenshot saved as debug_screenshot.png")
        
        # Get page title
        title = await page.title()
        print(f"Page title: {title}")
        
        # Check for common table selectors
        tables = await page.query_selector_all('table')
        print(f"Found {len(tables)} tables")
        
        # Check for pagination elements
        page_inputs = await page.query_selector_all('input[name="nowpage"]')
        print(f"Found {len(page_inputs)} page input fields")
        
        search_buttons = await page.query_selector_all('input[type="image"]')
        print(f"Found {len(search_buttons)} image input buttons")
        
        # Look for any data rows
        rows = await page.query_selector_all('tr')
        print(f"Found {len(rows)} table rows")
        
        # Get page content and save to file
        content = await page.content()
        with open('debug_page_content.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Page content saved as debug_page_content.html")
        
        # Check for any error messages or special content
        body_text = await page.text_content('body')
        if '검색 결과가 없습니다' in body_text:
            print("Found '검색 결과가 없습니다' message")
        
        if '공고' in body_text:
            print("Found '공고' text - notices may be present")
            
        # Wait for user to inspect
        print("Browser window opened. Press Enter after inspecting the page...")
        input()
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_page())