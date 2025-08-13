"""
Detail page data extractor for bankruptcy auction notices
"""
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from datetime import datetime
from utils.logger import setup_logger


class DetailExtractor:
    """Extracts detailed information from notice detail pages"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
    def extract_detail_data(self, html_content: str, notice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract detailed information from notice detail page"""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            detail_data = {
                'sequence_number': notice_data.get('sequence_number', ''),
                'extraction_date': datetime.now().isoformat(),
                'detail_url': '',
                'notice_content': '',
                'notice_date': '',
                'jurisdiction_full': '',
                'case_details': '',
                'attachment_links': [],
                'contact_info': '',
                'deadline_info': '',
                'additional_info': {}
            }
            
            # Extract main content
            detail_data['notice_content'] = self._extract_notice_content(soup)
            
            # Extract notice metadata
            detail_data.update(self._extract_notice_metadata(soup))
            
            # Extract attachment information
            detail_data['attachment_links'] = self._extract_attachment_links(soup)
            
            # Extract contact and deadline information
            detail_data['contact_info'] = self._extract_contact_info(soup)
            detail_data['deadline_info'] = self._extract_deadline_info(soup)
            
            # Extract additional structured information
            detail_data['additional_info'] = self._extract_additional_info(soup)
            
            self.logger.info(f"Extracted detail data for notice {detail_data['sequence_number']}")
            return detail_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract detail data: {e}")
            return {
                'sequence_number': notice_data.get('sequence_number', ''),
                'extraction_date': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def _extract_notice_content(self, soup: BeautifulSoup) -> str:
        """Extract main notice content"""
        
        try:
            # Look for common content containers
            content_selectors = [
                '.notice-content',
                '.content',
                '.board-content',
                'div[class*="content"]',
                'td[class*="content"]',
                '.post-content'
            ]
            
            content = ""
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True, separator='\n')
                    break
                    
            # Fallback: look for tables with content
            if not content:
                tables = soup.find_all('table')
                for table in tables:
                    table_text = table.get_text(strip=True, separator='\n')
                    if len(table_text) > 100:  # Assume content tables are longer
                        content = table_text
                        break
                        
            return self._clean_text(content)
            
        except Exception as e:
            self.logger.error(f"Error extracting notice content: {e}")
            return ""
            
    def _extract_notice_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract notice metadata (date, case details, etc.)"""
        
        metadata = {
            'notice_date': '',
            'jurisdiction_full': '',
            'case_details': '',
        }
        
        try:
            # Look for date information
            date_patterns = [
                r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',
                r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
                r'\d{1,2}[-./]\d{1,2}[-./]\d{4}'
            ]
            
            text_content = soup.get_text()
            for pattern in date_patterns:
                import re
                dates = re.findall(pattern, text_content)
                if dates:
                    metadata['notice_date'] = dates[0]
                    break
                    
            # Look for case numbers and details
            case_patterns = [
                r'\d{4}[가-힣]+\d+',  # e.g., 2024하합101142
                r'사건번호[:\s]*([^\s\n]+)',
                r'사건[:\s]*([^\s\n]+)'
            ]
            
            for pattern in case_patterns:
                import re
                cases = re.findall(pattern, text_content)
                if cases:
                    metadata['case_details'] = cases[0]
                    break
                    
            # Extract jurisdiction information
            jurisdiction_keywords = ['법원', '지원', '지청']
            for keyword in jurisdiction_keywords:
                if keyword in text_content:
                    # Extract surrounding context
                    import re
                    match = re.search(f'([^\\n]*{keyword}[^\\n]*)', text_content)
                    if match:
                        metadata['jurisdiction_full'] = match.group(1).strip()
                        break
                        
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            
        return metadata
        
    def _extract_attachment_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract attachment download links"""
        
        attachment_links = []
        
        try:
            # Method 1: JavaScript download functions
            js_download_links = soup.find_all('a', href=lambda x: x and 'download(' in x)
            
            for link in js_download_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Extract download parameters
                import re
                match = re.search(r"download\s*\(\s*['\"]([^'\"]+)['\"]?\s*,\s*['\"]([^'\"]+)['\"]?\s*\)", href)
                if match:
                    file_id = match.group(1)
                    display_name = match.group(2)
                    
                    attachment_links.append({
                        'type': 'javascript_download',
                        'file_id': file_id,
                        'display_name': display_name,
                        'link_text': text,
                        'href': href
                    })
                    
            # Method 2: Direct file links
            file_extensions = ['.pdf', '.doc', '.docx', '.hwp', '.zip', '.xlsx', '.xls']
            for ext in file_extensions:
                direct_links = soup.find_all('a', href=lambda x: x and ext in x.lower())
                
                for link in direct_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    attachment_links.append({
                        'type': 'direct_link',
                        'href': href,
                        'link_text': text,
                        'file_extension': ext
                    })
                    
            # Method 3: onclick handlers
            onclick_links = soup.find_all(['a', 'button'], onclick=lambda x: x and 'download' in x.lower())
            
            for link in onclick_links:
                onclick = link.get('onclick', '')
                text = link.get_text(strip=True)
                
                attachment_links.append({
                    'type': 'onclick_download',
                    'onclick': onclick,
                    'link_text': text
                })
                
        except Exception as e:
            self.logger.error(f"Error extracting attachment links: {e}")
            
        return attachment_links
        
    def _extract_contact_info(self, soup: BeautifulSoup) -> str:
        """Extract contact information"""
        
        try:
            text_content = soup.get_text()
            
            # Look for contact patterns
            contact_patterns = [
                r'연락처[:\s]*([^\n]+)',
                r'전화[:\s]*([^\n]+)',
                r'문의[:\s]*([^\n]+)',
                r'담당자[:\s]*([^\n]+)',
                r'\d{2,3}-\d{3,4}-\d{4}'  # Phone number pattern
            ]
            
            import re
            for pattern in contact_patterns:
                matches = re.findall(pattern, text_content)
                if matches:
                    return matches[0].strip()
                    
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting contact info: {e}")
            return ""
            
    def _extract_deadline_info(self, soup: BeautifulSoup) -> str:
        """Extract deadline and important date information"""
        
        try:
            text_content = soup.get_text()
            
            # Look for deadline patterns
            deadline_patterns = [
                r'마감[:\s]*([^\n]+)',
                r'기한[:\s]*([^\n]+)',
                r'까지[:\s]*([^\n]+)',
                r'신청기간[:\s]*([^\n]+)',
                r'접수기간[:\s]*([^\n]+)'
            ]
            
            import re
            for pattern in deadline_patterns:
                matches = re.findall(pattern, text_content)
                if matches:
                    return matches[0].strip()
                    
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting deadline info: {e}")
            return ""
            
    def _extract_additional_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract additional structured information"""
        
        additional_info = {}
        
        try:
            # Look for tables with structured data
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        
                        if key and value and len(key) < 50:  # Reasonable key length
                            additional_info[key] = value
                            
            # Look for definition lists
            dl_elements = soup.find_all('dl')
            for dl in dl_elements:
                dt_elements = dl.find_all('dt')
                dd_elements = dl.find_all('dd')
                
                for dt, dd in zip(dt_elements, dd_elements):
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    if key and value:
                        additional_info[key] = value
                        
        except Exception as e:
            self.logger.error(f"Error extracting additional info: {e}")
            
        return additional_info
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
            
        # Remove extra whitespace and normalize
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common unwanted characters
        text = text.replace('\xa0', ' ')  # Non-breaking space
        text = text.replace('\u200b', '')  # Zero-width space
        
        return text.strip()