"""
Data extractor for parsing auction notice information from HTML
"""
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime
from utils.logger import setup_logger


class DataExtractor:
    """Extracts auction data from HTML content"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
    def extract_auction_data(self, html_content: str, page_num: int) -> List[Dict[str, Any]]:
        """Extract auction notices from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            auction_data = []
            
            # Find the main table with auction data (use correct class)
            table = soup.find('table', class_='tableHor')
            if not table:
                self.logger.warning(f"No auction table found on page {page_num}")
                return auction_data
                
            # Find all data rows (skip header)
            tbody = table.find('tbody')
            if not tbody:
                self.logger.warning(f"No table body found on page {page_num}")
                return auction_data
                
            rows = tbody.find_all('tr')
            
            for row_idx, row in enumerate(rows):
                try:
                    cells = row.find_all('td')
                    
                    # Skip if not enough cells or if it's an empty/no-data row
                    if len(cells) < 5:
                        continue
                        
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    
                    # Skip rows with "검색 결과가 없습니다" or similar messages
                    if any("검색 결과가 없습니다" in text for text in cell_texts):
                        continue
                        
                    # Skip empty rows
                    if all(not text for text in cell_texts):
                        continue
                        
                    # Extract data from cells
                    auction_item = self._parse_auction_row(cells, page_num, row_idx + 1)
                    if auction_item:
                        auction_data.append(auction_item)
                        
                except Exception as e:
                    self.logger.error(f"Error parsing row {row_idx + 1} on page {page_num}: {e}")
                    continue
                    
            self.logger.info(f"Extracted {len(auction_data)} auction items from page {page_num}")
            return auction_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract data from page {page_num}: {e}")
            return []
            
    def _parse_auction_row(self, cells: List, page_num: int, row_num: int) -> Dict[str, Any]:
        """Parse individual auction row"""
        try:
            # Based on the typical structure of Korean court auction notices
            # Adjust indices based on actual table structure
            
            if len(cells) < 5:
                return None
                
            # Extract cell contents
            cell_contents = []
            for cell in cells:
                text = cell.get_text(strip=True)
                cell_contents.append(text)
                
            # Map to expected fields based on actual table structure
            # From HTML: 번호, 관할법원, 매각기관, 제목, 조회
            auction_item = {
                'page_number': page_num,
                'row_number': row_num,
                'extraction_date': datetime.now().isoformat(),
            }
            
            # Map fields based on the actual table structure
            if len(cell_contents) >= 5:
                auction_item.update({
                    'sequence_number': self._clean_text(cell_contents[0]),  # 번호
                    'jurisdiction': self._clean_text(cell_contents[1]),     # 관할법원
                    'bankruptcy_trustee': self._clean_text(cell_contents[2]), # 매각기관
                    'notice_title': self._clean_text(cell_contents[3]),     # 제목
                    'view_count': self._clean_text(cell_contents[4]),       # 조회
                })
            elif len(cell_contents) >= 3:
                # Fallback mapping for incomplete rows
                auction_item.update({
                    'sequence_number': self._clean_text(cell_contents[0]) if len(cell_contents) > 0 else '',
                    'jurisdiction': self._clean_text(cell_contents[1]) if len(cell_contents) > 1 else '',
                    'bankruptcy_trustee': self._clean_text(cell_contents[2]) if len(cell_contents) > 2 else '',
                    'notice_title': '',
                    'view_count': '',
                })
                
            # Add any additional fields if more columns exist
            if len(cell_contents) > 5:
                for i, content in enumerate(cell_contents[5:], start=5):
                    auction_item[f'additional_field_{i}'] = self._clean_text(content)
                    
            # Extract links if any
            links = []
            for cell in cells:
                cell_links = cell.find_all('a', href=True)
                for link in cell_links:
                    href = link.get('href')
                    if href:
                        links.append({
                            'text': link.get_text(strip=True),
                            'href': href
                        })
            
            if links:
                auction_item['links'] = links
                
            return auction_item
            
        except Exception as e:
            self.logger.error(f"Error parsing auction row {row_num}: {e}")
            return None
            
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
            
        # Remove extra whitespace and normalize
        text = " ".join(text.split())
        
        # Remove common unwanted characters
        text = text.replace('\xa0', ' ')  # Non-breaking space
        text = text.replace('\u200b', '')  # Zero-width space
        
        return text.strip()
        
    def extract_page_info(self, html_content: str) -> Dict[str, Any]:
        """Extract pagination and page information"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            page_info = {
                'current_page': 1,
                'total_pages': None,
                'has_next': False,
                'has_previous': False
            }
            
            # Try to find current page number
            page_input = soup.find('input', {'name': 'nowpage'})
            if page_input and page_input.get('value'):
                try:
                    page_info['current_page'] = int(page_input.get('value'))
                except ValueError:
                    pass
                    
            # Look for pagination controls
            pagination = soup.find('div', class_='paging') or soup.find('div', class_='pagination')
            if pagination:
                # Check for next/previous buttons
                next_btn = pagination.find('a', string='다음') or pagination.find('a', string='>')
                prev_btn = pagination.find('a', string='이전') or pagination.find('a', string='<')
                
                page_info['has_next'] = next_btn is not None
                page_info['has_previous'] = prev_btn is not None
                
            return page_info
            
        except Exception as e:
            self.logger.error(f"Failed to extract page info: {e}")
            return {'current_page': 1, 'total_pages': None, 'has_next': False, 'has_previous': False}