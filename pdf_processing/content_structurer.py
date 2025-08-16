"""
AI-powered PDF content structuring module
Converts raw text into structured JSON following the bankruptcy auction schema
"""
import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from utils.logger import setup_logger


@dataclass
class StructuringResult:
    """Result of content structuring operation"""
    success: bool
    structured_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    confidence_score: float
    processing_notes: List[str]


class ContentStructurer:
    """AI-powered content structurer for bankruptcy auction documents"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.schema_version = "1.0"
        
    def structure_document(self, notice_id: str, file_name: str, 
                          text_blocks: List[str], tables: List[Dict]) -> StructuringResult:
        """
        Structure document content into JSON format
        
        Args:
            notice_id: Notice ID
            file_name: PDF file name
            text_blocks: List of extracted text blocks
            tables: List of extracted tables
            
        Returns:
            StructuringResult with structured data
        """
        try:
            self.logger.info(f"Starting content structuring for {file_name}")
            
            # Combine all text for analysis
            full_text = self._combine_text_blocks(text_blocks)
            
            # Extract structured data using pattern matching and AI logic
            structured_data = self._extract_structured_data(
                notice_id, file_name, full_text, tables
            )
            
            # Validate and clean the structured data
            validated_data = self._validate_structured_data(structured_data)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(validated_data, full_text)
            
            processing_notes = [
                f"Processed {len(text_blocks)} text blocks",
                f"Processed {len(tables)} tables",
                f"Confidence score: {confidence:.2f}"
            ]
            
            return StructuringResult(
                success=True,
                structured_data=validated_data,
                error_message=None,
                confidence_score=confidence,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            self.logger.error(f"Content structuring failed for {file_name}: {e}")
            return StructuringResult(
                success=False,
                structured_data=None,
                error_message=str(e),
                confidence_score=0.0,
                processing_notes=[f"Error: {str(e)}"]
            )
    
    def _combine_text_blocks(self, text_blocks: List[str]) -> str:
        """Combine text blocks into a single document"""
        return "\n".join([block.strip() for block in text_blocks if block.strip()])
    
    def _extract_structured_data(self, notice_id: str, file_name: str, 
                                full_text: str, tables: List[Dict]) -> Dict[str, Any]:
        """Extract structured data using pattern matching and heuristics"""
        
        # Split text into sections
        section_texts = self._split_text_by_sections(full_text)
        
        # Initialize base structure
        structured = {
            "schema_version": self.schema_version,
            "document_meta": {
                "file_name": file_name,
                "title": self._extract_title(full_text),
                "created_at": self._extract_date(full_text),
                "pages": None,
                "notes": None
            },
            "sections": {
                "매각대상자산": self._extract_asset_info(section_texts.get("매각대상자산", ""), tables),
                "입찰방법_최저입찰가": self._extract_bidding_info(section_texts.get("입찰방법_최저입찰가", ""), tables),
                "입찰참가자격_방법": self._extract_participation_info(section_texts.get("입찰참가자격_방법", "")),
                "계약체결_대금납부": self._extract_contract_info(section_texts.get("계약체결_대금납부", "")),
                "유의사항": self._extract_precautions(section_texts.get("유의사항", "")),
                "기타사항_문의": self._extract_contact_info(section_texts.get("기타사항_문의", ""))
            },
            "quality": {
                "missing_sections": [],
                "parse_error": [],
                "notes": None
            }
        }
        
        # Check for missing sections
        structured["quality"]["missing_sections"] = self._find_missing_sections(full_text)
        
        return structured
    
    def _split_text_by_sections(self, text: str) -> Dict[str, str]:
        """Split full text into sections based on Korean document structure"""
        sections = {
            "매각대상자산": "",
            "입찰방법_최저입찰가": "",
            "입찰참가자격_방법": "",
            "계약체결_대금납부": "",
            "유의사항": "",
            "기타사항_문의": ""
        }
        
        # Section patterns with variations - more precise matching
        section_patterns = [
            # 매각대상자산
            (r"1\s*\.\s*매각\s*대상(?:\s*자산)?", "매각대상자산"),
            # 입찰방법 및 최저입찰가
            (r"2\s*\.\s*(?:입찰\s*방법|최저.*입찰가)", "입찰방법_최저입찰가"),
            # 입찰참가자격 및 방법
            (r"3\s*\.\s*입찰\s*참가", "입찰참가자격_방법"),
            # 계약체결 및 대금납부
            (r"4\s*\.\s*(?:계약\s*체결|대금.*납부)", "계약체결_대금납부"),
            # 유의사항
            (r"5\s*\.\s*유의\s*사항", "유의사항"),
            # 기타사항 및 문의
            (r"6\s*\.\s*(?:기타.*사항|문의)", "기타사항_문의")
        ]
        
        # Split text by sections using more intelligent approach
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line matches any section pattern
            matched_section = None
            for pattern, section_name in section_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matched_section = section_name
                    break
            
            if matched_section:
                # Save previous section content
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content)
                
                # Start new section
                current_section = matched_section
                section_content = [line]
            else:
                # Add line to current section
                if current_section:
                    section_content.append(line)
                else:
                    # Smart content classification for lines without clear section headers
                    if re.search(r'매각\s*대상.*자산|공유\s*특허|※.*특허|특허권.*공유', line, re.IGNORECASE):
                        if not sections["매각대상자산"]:
                            sections["매각대상자산"] = line + '\n'
                        else:
                            sections["매각대상자산"] += line + '\n'
                    elif re.search(r'일반.*경쟁.*입찰|전자.*입찰|입찰.*방법', line, re.IGNORECASE):
                        sections["입찰방법_최저입찰가"] += line + '\n'
                    elif re.search(r'입찰.*참가|공인.*인증|온비드|회원.*등록', line, re.IGNORECASE):
                        sections["입찰참가자격_방법"] += line + '\n'
                    elif re.search(r'계약.*체결|대금.*납부|낙찰.*결과|매매.*계약', line, re.IGNORECASE):
                        sections["계약체결_대금납부"] += line + '\n'
                    elif re.search(r'유의.*사항|무효.*처리|입찰.*보증금|반환', line, re.IGNORECASE):
                        sections["유의사항"] += line + '\n'
                    elif re.search(r'문의|연락|전화|관재인|변호사|http|콜센터', line, re.IGNORECASE):
                        sections["기타사항_문의"] += line + '\n'
        
        # Save last section content
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content)
        
        # Clean up sections
        for section_name in sections:
            sections[section_name] = sections[section_name].strip()
            
        return sections
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract document title"""
        # Look for common title patterns
        patterns = [
            r'자산\s*매각\s*공고',
            r'매각\s*공고',
            r'특허권.*매각',
            r'공유특허권.*매각'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Try to get more context around the match
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()
                return context
                
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract creation date"""
        # Look for date patterns
        date_patterns = [
            r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})\.(\d{2})\.(\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                year, month, day = match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
        return None
    
    def _extract_asset_info(self, text: str, tables: List[Dict]) -> Dict[str, Any]:
        """Extract asset information from section 1"""
        section = {
            "asset_type": None,
            "assets": [],
            "general_notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Extract asset type - improved patterns
        asset_type_patterns = [
            r'매각\s*대상\s*자산\s*[:：]\s*([^\n\r\.]+)',
            r'매각\s*대상\s*[:：]\s*([^\n\r\.]+)',
            r'자산\s*[:：]\s*([^\n\r\.]+)',
            r'1\.\s*매각\s*대상\s*자산\s*[:：]\s*([^\n\r\.]+)',
            r'([가-힣]+특허권)',  # 공유특허권, 특허권 등 직접 매칭
        ]
        
        for pattern in asset_type_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                asset_type = match.group(1).strip()
                if asset_type and len(asset_type) > 1:  # 의미있는 내용만
                    section["asset_type"] = asset_type
                    break
        
        # Extract general notes from section-specific content only
        if text.strip():  # Only if there's actual text in this section
            notes_patterns = [
                r'※\s*([^※]+?)(?=※|\n\n|\Z)',
                r'매각대상.*?특허권.*?([^.\n]+\.)',
                r'채무자.*?공유.*?([^.\n]+\.)',
                r'([^\n]*(?:공유|특허|자산)[^\n]*)'
            ]
            
            notes_list = []
            for pattern in notes_patterns:
                matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    note = match.group(1).strip()
                    if len(note) > 10 and note not in notes_list:  # Avoid duplicates
                        notes_list.append(note)
            
            if notes_list:
                section["general_notes"] = "\n".join(notes_list[:3])  # Limit to first 3 relevant notes
            else:
                # If no specific patterns found, use cleaned section text
                clean_text = re.sub(r'\s+', ' ', text).strip()
                if len(clean_text) > 20:  # Only store meaningful content
                    section["general_notes"] = clean_text[:500]  # Limit length
        
        # Process tables for asset details
        if tables:
            section["assets"] = self._process_asset_tables(tables)
        
        return section
    
    def _process_asset_tables(self, tables: List[Dict]) -> List[Dict[str, Any]]:
        """Process tables to extract asset details"""
        assets = []
        
        for i, table in enumerate(tables):
            if not table.get('data'):
                continue
                
            table_data = table['data']
            
            # Check if this looks like an asset table
            if self._is_asset_table(table_data):
                asset_rows = self._parse_asset_table(table_data)
                assets.extend(asset_rows)
        
        return assets
    
    def _is_asset_table(self, table_data: List[List[str]]) -> bool:
        """Check if table contains asset information"""
        if not table_data or len(table_data) < 2:
            return False
            
        header_text = " ".join([cell.lower() for row in table_data[:2] for cell in row])
        
        asset_keywords = ['등록번호', '출원일', '등록일', '특허', '발명', '연차료']
        return any(keyword in header_text for keyword in asset_keywords)
    
    def _parse_asset_table(self, table_data: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse asset table into structured format"""
        assets = []
        
        if not table_data:
            return assets
            
        # Try to identify column headers
        headers = []
        for row in table_data[:3]:  # Check first 3 rows for headers
            for cell in row:
                cell_lower = cell.lower().strip()
                if any(keyword in cell_lower for keyword in ['등록번호', '출원일', '등록일', '발명']):
                    headers = row
                    break
            if headers:
                break
        
        # If no clear headers, create default structure
        if not headers and table_data:
            # Assume standard format
            for i, row in enumerate(table_data[1:], 1):  # Skip header row
                if len(row) >= 2:
                    asset = {
                        "seq": i,
                        "registration_no": row[0] if row[0] else None,
                        "title": row[1] if len(row) > 1 and row[1] else None,
                        "application_date": self._extract_date_from_cell(row[2]) if len(row) > 2 else None,
                        "registration_date": self._extract_date_from_cell(row[3]) if len(row) > 3 else None,
                        "remark": row[4] if len(row) > 4 and row[4] else None,
                        "annual_fee_extra_deadline": None,
                        "page": None,
                        "bbox": None,
                        "confidence": 0.8,
                        "recommended": None,
                        "recommendation_reason": None,
                        "source_text": " | ".join(row),
                        "additional_fields": {}
                    }
                    assets.append(asset)
        
        return assets
    
    def _extract_date_from_cell(self, cell: str) -> Optional[str]:
        """Extract date from table cell"""
        if not cell:
            return None
            
        # Look for date patterns in cell
        date_patterns = [
            r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})',
            r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, cell)
            if match:
                year, month, day = match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
        return None
    
    def _extract_bidding_info(self, text: str, tables: List[Dict]) -> Dict[str, Any]:
        """Extract bidding information from section 2"""
        section = {
            "bidding_type": self._find_pattern(text, r'입찰\s*방법\s*:\s*([^\n\r]+)'),
            "bid_period_start": None,
            "bid_period_end": None,
            "platform": self._find_pattern(text, r'입찰\s*사이트\s*:\s*([^\n\r]+)'),
            "opening_place": None,
            "rounds": [],
            "asset_publication": None,
            "notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Extract bidding type from various patterns
        if not section["bidding_type"]:
            bidding_patterns = [
                r'(일반\s*공개\s*경쟁\s*입찰)',
                r'(공개\s*경쟁\s*입찰)',
                r'(전자\s*입찰)',
                r'(서면\s*입찰)',
                r'입찰\s*방법\s*[:：]\s*([^\n\r]+)'
            ]
            for pattern in bidding_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    bidding_type = match.group(1).strip()
                    if bidding_type and len(bidding_type) > 2:
                        section["bidding_type"] = bidding_type
                        break
        
        # Add section-specific notes
        if text.strip():
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 20:
                section["notes"] = clean_text[:500]
        
        return section
    
    def _extract_participation_info(self, text: str) -> Dict[str, Any]:
        """Extract participation information from section 3"""
        section = {
            "is_electronic_only": None,
            "platform_url": self._find_pattern(text, r'https?://[^\s]+'),
            "auth_requirement": None,
            "award_rule": None,
            "tie_break_rule": None,
            "multiple_bid_restriction": None,
            "time_standard": None,
            "joint_bid_allowed": None,
            "notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Add section-specific notes
        if text.strip():
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 20:
                section["notes"] = clean_text[:500]
        
        return section
    
    def _extract_contract_info(self, text: str) -> Dict[str, Any]:
        """Extract contract information from section 4"""
        section = {
            "contract_sign_deadline_rule": None,
            "payment_deadline_rule": None,
            "court_approval_required": None,
            "ownership_transfer_deadline_rule": None,
            "forfeiture_conditions": None,
            "notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Add section-specific notes
        if text.strip():
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 20:
                section["notes"] = clean_text[:500]
        
        return section
    
    def _extract_precautions(self, text: str) -> Dict[str, Any]:
        """Extract precautions from section 5"""
        section = {
            "invalid_bid_conditions": [],
            "responsibilities": [],
            "tax_invoice_available": None,
            "refund_policy": None,
            "private_treaty_possible": None,
            "bid_delay_or_cancellation_rule": None,
            "notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Add section-specific notes
        if text.strip():
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 20:
                section["notes"] = clean_text[:500]
        
        return section
    
    def _extract_contact_info(self, text: str) -> Dict[str, Any]:
        """Extract contact information from section 6"""
        section = {
            "platform_help": {
                "name": None,
                "url": self._find_pattern(text, r'https?://[^\s]+'),
                "call_center": None
            },
            "trustee_contact": {
                "organization": self._find_pattern(text, r'(법무법인\s*[^\n\r]+|변호사\s*[가-힣\s]+)'),
                "name_or_role": None,
                "phone": self._find_pattern(text, r'(\d{2,3}-\d{3,4}-\d{4})'),
                "fax": self._find_pattern(text, r'팩스\s*[:：]\s*(\d{2,3}-\d{3,4}-\d{4})')
            },
            "notes": None,
            "extras": {},
            "unmapped": []
        }
        
        # Add section-specific notes
        if text.strip():
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) > 20:
                section["notes"] = clean_text[:500]
        
        return section
    
    def _find_pattern(self, text: str, pattern: str) -> Optional[str]:
        """Find pattern in text and return the first match"""
        try:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and len(match.groups()) > 0:
                return match.group(1).strip()
        except Exception as e:
            self.logger.error(f"Pattern matching error for pattern '{pattern}': {e}")
        return None
    
    def _find_missing_sections(self, text: str) -> List[int]:
        """Find which sections are missing from the document"""
        section_patterns = [
            (1, r'매각\s*대상|자산'),
            (2, r'입찰\s*방법|최저.*입찰가'),
            (3, r'입찰.*참가|자격'),
            (4, r'계약\s*체결|대금\s*납부'),
            (5, r'유의\s*사항'),
            (6, r'기타.*사항|문의')
        ]
        
        missing = []
        for section_num, pattern in section_patterns:
            if not re.search(pattern, text, re.IGNORECASE):
                missing.append(section_num)
        
        return missing
    
    def _validate_structured_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean structured data"""
        # Ensure required structure exists
        if "sections" not in data:
            data["sections"] = {}
        
        if "quality" not in data:
            data["quality"] = {
                "missing_sections": [],
                "parse_error": [],
                "notes": None
            }
        
        return data
    
    def _calculate_confidence(self, structured_data: Dict[str, Any], full_text: str) -> float:
        """Calculate confidence score for the structured data"""
        confidence = 0.0
        total_checks = 0
        
        # Check if key sections have data
        sections = structured_data.get("sections", {})
        
        # Section 1 (매각대상자산)
        if sections.get("1_매각대상자산", {}).get("asset_type"):
            confidence += 0.3
        total_checks += 0.3
        
        # Section 2 (입찰방법)
        if sections.get("2_입찰방법_최저입찰가", {}).get("bidding_type"):
            confidence += 0.2
        total_checks += 0.2
        
        # Contact info
        if sections.get("6_기타사항_문의", {}).get("trustee_contact", {}).get("organization"):
            confidence += 0.2
        total_checks += 0.2
        
        # Title extraction
        if structured_data.get("document_meta", {}).get("title"):
            confidence += 0.1
        total_checks += 0.1
        
        # Missing sections penalty
        missing_count = len(structured_data.get("quality", {}).get("missing_sections", []))
        confidence -= missing_count * 0.05
        
        # Text content richness
        if len(full_text) > 1000:
            confidence += 0.1
        total_checks += 0.1
        
        # General notes (특허권 공유 관련)
        if "공유" in full_text and "특허권" in full_text:
            confidence += 0.1
        total_checks += 0.1
        
        return min(1.0, max(0.0, confidence))