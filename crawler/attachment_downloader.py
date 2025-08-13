"""
Attachment downloader for bankruptcy auction notices
"""
import os
import re
import asyncio
# import aiofiles  # Not needed for this implementation
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from pathlib import Path
from playwright.async_api import Page
from utils.logger import setup_logger
from config import DELAY_BETWEEN_REQUESTS


class AttachmentDownloader:
    """Downloads attachments from notice detail pages"""
    
    def __init__(self, downloads_dir: str = "downloads"):
        self.logger = setup_logger(__name__)
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(exist_ok=True)
        
    async def download_notice_attachments(self, 
                                        page: Page, 
                                        notice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Download all attachments for a specific notice"""
        
        sequence_number = notice_data.get('sequence_number', 'unknown')
        notice_title = notice_data.get('notice_title', 'untitled')
        
        # Create directory for this notice
        notice_dir = self.downloads_dir / f"notice_{sequence_number}_{self._sanitize_filename(notice_title)}"
        notice_dir.mkdir(exist_ok=True)
        
        attachments_info = {
            'notice_sequence': sequence_number,
            'notice_title': notice_title,
            'notice_dir': str(notice_dir),
            'attachments': [],
            'download_errors': []
        }
        
        try:
            # Find attachment links on the page
            attachment_links = await self._find_attachment_links(page)
            
            if not attachment_links:
                self.logger.info(f"No attachments found for notice {sequence_number}")
                return attachments_info
                
            self.logger.info(f"Found {len(attachment_links)} attachments for notice {sequence_number}")
            
            # Download each attachment
            for i, link_info in enumerate(attachment_links):
                try:
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS / 2)  # Shorter delay between downloads
                    
                    attachment_info = await self._download_single_attachment(
                        page, link_info, notice_dir, i + 1
                    )
                    
                    if attachment_info:
                        attachments_info['attachments'].append(attachment_info)
                        self.logger.info(f"Downloaded: {attachment_info['filename']}")
                    
                except Exception as e:
                    error_msg = f"Failed to download attachment {i+1}: {e}"
                    self.logger.error(error_msg)
                    attachments_info['download_errors'].append({
                        'attachment_index': i + 1,
                        'error': str(e),
                        'link_info': link_info
                    })
                    
        except Exception as e:
            self.logger.error(f"Error downloading attachments for notice {sequence_number}: {e}")
            attachments_info['download_errors'].append({
                'general_error': str(e)
            })
            
        return attachments_info
        
    async def _find_attachment_links(self, page: Page) -> List[Dict[str, str]]:
        """Find all attachment download links on the page"""
        
        attachment_links = []
        
        try:
            # Method 1: Look for JavaScript download functions
            # Pattern: download('file_id', 'display_name')
            js_download_links = await page.query_selector_all('a[href*="javascript:download"]')
            
            for link in js_download_links:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href and 'download' in href:
                    # Extract file information from JavaScript call
                    match = re.search(r"download\s*\(\s*['\"]([^'\"]+)['\"]?\s*,\s*['\"]([^'\"]+)['\"]?\s*\)", href)
                    if match:
                        file_id = match.group(1)
                        display_name = match.group(2)
                        
                        attachment_links.append({
                            'type': 'javascript_download',
                            'file_id': file_id,
                            'display_name': display_name,
                            'link_text': text.strip(),
                            'href': href
                        })
                        
            # Method 2: Look for direct file links
            direct_file_links = await page.query_selector_all('a[href*=".pdf"], a[href*=".doc"], a[href*=".hwp"], a[href*=".zip"], a[href*=".xlsx"], a[href*=".xls"]')
            
            for link in direct_file_links:
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href:
                    attachment_links.append({
                        'type': 'direct_link',
                        'href': href,
                        'link_text': text.strip(),
                        'filename': os.path.basename(urlparse(href).path)
                    })
                    
            # Method 3: Look for form-based downloads
            form_download_links = await page.query_selector_all('a[onclick*="download"], button[onclick*="download"]')
            
            for link in form_download_links:
                onclick = await link.get_attribute('onclick')
                text = await link.text_content()
                
                if onclick and 'download' in onclick:
                    attachment_links.append({
                        'type': 'onclick_download',
                        'onclick': onclick,
                        'link_text': text.strip()
                    })
                    
        except Exception as e:
            self.logger.error(f"Error finding attachment links: {e}")
            
        return attachment_links
        
    async def _download_single_attachment(self, 
                                        page: Page, 
                                        link_info: Dict[str, str], 
                                        notice_dir: Path, 
                                        index: int) -> Optional[Dict[str, Any]]:
        """Download a single attachment file"""
        
        try:
            if link_info['type'] == 'javascript_download':
                return await self._download_javascript_file(page, link_info, notice_dir, index)
            elif link_info['type'] == 'direct_link':
                return await self._download_direct_file(page, link_info, notice_dir, index)
            elif link_info['type'] == 'onclick_download':
                return await self._download_onclick_file(page, link_info, notice_dir, index)
            else:
                self.logger.warning(f"Unknown attachment type: {link_info['type']}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading attachment: {e}")
            return None
            
    async def _download_javascript_file(self, 
                                      page: Page, 
                                      link_info: Dict[str, str], 
                                      notice_dir: Path, 
                                      index: int) -> Optional[Dict[str, Any]]:
        """Download file using JavaScript download function"""
        
        try:
            file_id = link_info['file_id']
            display_name = link_info['display_name']
            
            # Sanitize filename
            safe_filename = self._sanitize_filename(display_name)
            if not safe_filename.lower().endswith(('.pdf', '.doc', '.docx', '.hwp', '.zip', '.xlsx', '.xls')):
                # Try to extract extension from file_id or add .pdf as default
                if '.' in file_id:
                    ext = '.' + file_id.split('.')[-1]
                    safe_filename += ext
                else:
                    safe_filename += '.pdf'
                    
            file_path = notice_dir / f"{index:02d}_{safe_filename}"
            
            # Set up download handling
            async with page.expect_download() as download_info:
                # Execute the download JavaScript
                await page.evaluate(f"download('{file_id}', '{display_name}')")
                
            download = await download_info.value
            
            # Save the file
            await download.save_as(file_path)
            
            # Get file stats
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            return {
                'filename': file_path.name,
                'display_name': display_name,
                'file_path': str(file_path),
                'file_size': file_size,
                'download_method': 'javascript',
                'file_id': file_id
            }
            
        except Exception as e:
            self.logger.error(f"Error downloading JavaScript file: {e}")
            return None
            
    async def _download_direct_file(self, 
                                  page: Page, 
                                  link_info: Dict[str, str], 
                                  notice_dir: Path, 
                                  index: int) -> Optional[Dict[str, Any]]:
        """Download file using direct link"""
        
        try:
            href = link_info['href']
            filename = link_info.get('filename', f'attachment_{index}')
            
            # Handle relative URLs
            if href.startswith('/'):
                base_url = f"{page.url.split('/')[0]}//{page.url.split('/')[2]}"
                full_url = urljoin(base_url, href)
            else:
                full_url = href
                
            safe_filename = self._sanitize_filename(filename)
            file_path = notice_dir / f"{index:02d}_{safe_filename}"
            
            # Set up download handling
            async with page.expect_download() as download_info:
                await page.goto(full_url)
                
            download = await download_info.value
            await download.save_as(file_path)
            
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            return {
                'filename': file_path.name,
                'original_url': full_url,
                'file_path': str(file_path),
                'file_size': file_size,
                'download_method': 'direct'
            }
            
        except Exception as e:
            self.logger.error(f"Error downloading direct file: {e}")
            return None
            
    async def _download_onclick_file(self, 
                                   page: Page, 
                                   link_info: Dict[str, str], 
                                   notice_dir: Path, 
                                   index: int) -> Optional[Dict[str, Any]]:
        """Download file using onclick handler"""
        
        try:
            onclick = link_info['onclick']
            link_text = link_info['link_text']
            
            safe_filename = self._sanitize_filename(link_text) or f'attachment_{index}'
            if not safe_filename.lower().endswith(('.pdf', '.doc', '.docx', '.hwp', '.zip', '.xlsx', '.xls')):
                safe_filename += '.pdf'
                
            file_path = notice_dir / f"{index:02d}_{safe_filename}"
            
            # Set up download handling
            async with page.expect_download() as download_info:
                # Execute the onclick JavaScript
                await page.evaluate(onclick)
                
            download = await download_info.value
            await download.save_as(file_path)
            
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            return {
                'filename': file_path.name,
                'link_text': link_text,
                'file_path': str(file_path),
                'file_size': file_size,
                'download_method': 'onclick',
                'onclick_code': onclick
            }
            
        except Exception as e:
            self.logger.error(f"Error downloading onclick file: {e}")
            return None
            
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system storage"""
        if not filename:
            return ""
            
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
            
        # Remove extra whitespace and truncate if too long
        filename = re.sub(r'\s+', ' ', filename.strip())
        
        # Truncate if too long (keep extension)
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
            
        return filename
        
    def get_download_summary(self, attachments_info_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of all downloads"""
        
        total_notices = len(attachments_info_list)
        total_attachments = sum(len(info['attachments']) for info in attachments_info_list)
        total_errors = sum(len(info['download_errors']) for info in attachments_info_list)
        total_size = sum(
            att['file_size'] 
            for info in attachments_info_list 
            for att in info['attachments']
        )
        
        return {
            'total_notices_processed': total_notices,
            'total_attachments_downloaded': total_attachments,
            'total_download_errors': total_errors,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'notices_with_attachments': len([info for info in attachments_info_list if info['attachments']]),
            'notices_without_attachments': len([info for info in attachments_info_list if not info['attachments']])
        }