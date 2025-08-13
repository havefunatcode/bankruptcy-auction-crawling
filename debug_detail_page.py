"""
Debug script to analyze detail page structure and attachments
"""
import asyncio
from playwright.async_api import async_playwright


async def debug_detail_page():
    """Debug the detail page structure to understand attachment patterns"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale='ko-KR')
        page = await context.new_page()
        
        # First go to main page
        main_url = "https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work"
        print(f"Navigating to main page: {main_url}")
        await page.goto(main_url)
        await page.wait_for_load_state('networkidle')
        
        # Click on first notice link to get to detail page
        first_notice_link = await page.query_selector('table.tableHor tbody tr:first-child a')
        if first_notice_link:
            href = await first_notice_link.get_attribute('href')
            text = await first_notice_link.text_content()
            print(f"Found notice link: '{text}' -> {href}")
            print("Clicking on first notice link...")
            
            # Open in new tab to preserve session
            new_page = await context.new_page()
            await first_notice_link.click()
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)  # Give more time for navigation
            
            # Check current URL
            current_url = page.url
            print(f"Current URL after click: {current_url}")
            
            # Check page title
            title = await page.title()
            print(f"Page title: {title}")
        else:
            print("No notice link found!")
            return
        
        # Wait for page to load
        await page.wait_for_load_state('networkidle')
        
        # Take screenshot
        await page.screenshot(path="detail_page_screenshot.png")
        print("Screenshot saved as detail_page_screenshot.png")
        
        # Look for attachment links
        attachment_links = await page.query_selector_all('a[href*="download"], a[href*="file"], a[href*="attach"]')
        print(f"Found {len(attachment_links)} potential attachment links")
        
        # Look for common attachment patterns
        all_links = await page.query_selector_all('a[href]')
        print(f"Total links found: {len(all_links)}")
        
        attachment_candidates = []
        for link in all_links:
            href = await link.get_attribute('href')
            text = await link.text_content()
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.hwp', '.zip', '.xlsx', '.xls']) or \
               any(word in text for word in ['첨부', '다운로드', '파일', '양식']):
                attachment_candidates.append({
                    'href': href,
                    'text': text.strip()
                })
        
        print(f"\nAttachment candidates:")
        for i, candidate in enumerate(attachment_candidates):
            print(f"{i+1}. Text: '{candidate['text']}' -> {candidate['href']}")
        
        # Look for tables that might contain file information
        tables = await page.query_selector_all('table')
        print(f"\nFound {len(tables)} tables")
        
        # Save page content for analysis
        content = await page.content()
        with open('detail_page_content.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Detail page content saved as detail_page_content.html")
        
        # Look for specific patterns in the HTML
        if '첨부파일' in content:
            print("Found '첨부파일' text in page")
        if 'download' in content.lower():
            print("Found 'download' text in page")
        if '.pdf' in content.lower():
            print("Found PDF references in page")
            
        # Check for form-based downloads
        forms = await page.query_selector_all('form')
        print(f"Found {len(forms)} forms")
        
        for i, form in enumerate(forms):
            action = await form.get_attribute('action')
            method = await form.get_attribute('method')
            print(f"Form {i+1}: action='{action}', method='{method}'")
        
        print("\nBrowser window opened. Press Enter after inspecting...")
        input()
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_detail_page())