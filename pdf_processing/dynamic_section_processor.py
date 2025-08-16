"""
Dynamic Section-based PDF Content Processor
Dynamically identifies and structures PDF sections without predefined schema
"""
import re
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from utils.logger import setup_logger


@dataclass
class SectionContent:
    """Represents content within a document section"""
    section_name: str
    text_content: str
    tables: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    subsections: Dict[str, 'SectionContent']
    metadata: Dict[str, Any]


@dataclass
class ProcessingResult:
    """Result of dynamic section processing"""
    success: bool
    sections: Dict[str, SectionContent]
    document_metadata: Dict[str, Any]
    processing_notes: List[str]
    confidence_score: float
    error_message: Optional[str] = None


class DynamicSectionProcessor:
    """Processes PDF content into dynamic section-based structure"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Common section headers patterns (Korean documents)
        self.section_patterns = [
            # Numbered sections
            r'^(\d+)\s*[\.]\s*([^\n\r]+)',
            # Roman numerals
            r'^([IVX]+)\s*[\.]\s*([^\n\r]+)',
            # Korean numbering
            r'^([가-힣])\s*[\.]\s*([^\n\r]+)',
            # Bullet points
            r'^[○●▪▫■□◦‣]\s*([^\n\r]+)',
            # Headers with special characters
            r'^[※▶◆★☆]\s*([^\n\r]+)',
            # Bold/emphasized text (approximation)
            r'^【([^】]+)】',
            r'^\[([^\]]+)\]',
            # Double line breaks indicating section headers
            r'^([가-힣\s]+)(?=\n\s*\n)',
        ]
        
        # Subsection patterns
        self.subsection_patterns = [
            r'^(\d+)-(\d+)\s*[\.]\s*([^\n\r]+)',  # 1-1. subsection
            r'^([가-힣])-([가-힣])\s*[\.]\s*([^\n\r]+)',  # 가-나. subsection
            r'^\s*-\s*([^\n\r]+)',  # - bullet subsection
            r'^\s*\*\s*([^\n\r]+)',  # * bullet subsection
        ]
        
        # Content type classifiers
        self.content_classifiers = {
            'table_indicators': [
                r'표\s*\d+', r'table\s*\d+', r'\|.*\|', r'─+', r'━+',
                r'┌.*┐', r'├.*┤', r'└.*┘'
            ],
            'list_indicators': [
                r'^\s*[1-9]\d*\s*[).]', r'^\s*[가-힣]\s*[).]',
                r'^\s*[IVX]+\s*[).]', r'^\s*[○●▪▫■□]\s*'
            ],
            'important_content': [
                r'※\s*주의\s*사항', r'※\s*참고', r'※\s*유의',
                r'중요\s*사항', r'필수\s*사항', r'주의\s*:\s*'
            ],
            'contact_info': [
                r'\d{2,3}-\d{3,4}-\d{4}', r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                r'http[s]?://[^\s]+', r'연락처', r'문의', r'담당자'
            ],
            'dates': [
                r'\d{4}[년.-]\d{1,2}[월.-]\d{1,2}[일]?',
                r'\d{4}-\d{2}-\d{2}', r'\d{4}\.\d{2}\.\d{2}'
            ],
            'financial': [
                r'\d+,?\d*\s*원', r'\d+,?\d*\s*만원', r'\d+,?\d*\s*억원',
                r'입찰', r'낙찰', r'보증금', r'대금', r'수수료'
            ]
        }
    
    def process_document(self, notice_id: str, file_name: str, 
                        text_blocks: List[str], 
                        tables: List[Dict[str, Any]], 
                        images: List[Dict[str, Any]]) -> ProcessingResult:
        """
        Process document into dynamic section-based structure
        
        Args:
            notice_id: Notice ID
            file_name: PDF file name
            text_blocks: List of extracted text blocks
            tables: List of extracted tables with metadata
            images: List of extracted images with metadata
            
        Returns:
            ProcessingResult with dynamic sections
        """
        try:
            self.logger.info(f"Starting dynamic section processing for {file_name}")
            
            # Combine text blocks into full document text
            full_text = self._combine_text_blocks(text_blocks)
            
            # Detect sections dynamically
            sections = self._detect_sections(full_text)
            
            # Assign content to sections
            sections_with_content = self._assign_content_to_sections(
                sections, text_blocks, tables, images
            )
            
            # Extract document metadata
            doc_metadata = self._extract_document_metadata(full_text, file_name)
            
            # Calculate processing confidence
            confidence = self._calculate_confidence(sections_with_content, full_text)
            
            # Generate processing notes
            processing_notes = self._generate_processing_notes(
                sections_with_content, len(text_blocks), len(tables), len(images)
            )
            
            return ProcessingResult(
                success=True,
                sections=sections_with_content,
                document_metadata=doc_metadata,
                processing_notes=processing_notes,
                confidence_score=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Dynamic section processing failed for {file_name}: {e}")
            return ProcessingResult(
                success=False,
                sections={},
                document_metadata={},
                processing_notes=[f"Processing error: {str(e)}"],
                confidence_score=0.0,
                error_message=str(e)
            )
    
    def _combine_text_blocks(self, text_blocks: List[str]) -> str:
        """Combine text blocks preserving structure"""
        return "\n".join([block.strip() for block in text_blocks if block.strip()])
    
    def _detect_sections(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Dynamically detect sections in the document"""
        sections = {}
        lines = text.split('\n')
        
        current_section = None
        section_content = []
        section_counter = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if line matches any section pattern
            section_match = self._match_section_pattern(line)
            
            if section_match:
                # Save previous section if exists
                if current_section and section_content:
                    sections[current_section] = {
                        'title': current_section,
                        'start_line': sections.get(current_section, {}).get('start_line', i),
                        'content_lines': section_content.copy(),
                        'raw_content': '\n'.join(section_content),
                        'section_type': self._classify_section_type(current_section, section_content)
                    }
                
                # Start new section
                section_counter += 1
                section_name = section_match['clean_title']
                
                # Create unique section key
                section_key = f"section_{section_counter}_{self._normalize_section_name(section_name)}"
                
                current_section = section_key
                sections[current_section] = {
                    'title': section_name,
                    'start_line': i,
                    'original_title': section_match['original_line'],
                    'section_number': section_match.get('section_number'),
                    'content_lines': [],
                    'raw_content': '',
                    'section_type': 'unknown'
                }
                section_content = []
                
            else:
                # Add line to current section
                if current_section:
                    section_content.append(line)
                else:
                    # Content before first section - create preamble section
                    if 'preamble' not in sections:
                        sections['preamble'] = {
                            'title': '문서 서문',
                            'start_line': 0,
                            'content_lines': [],
                            'raw_content': '',
                            'section_type': 'preamble'
                        }
                        current_section = 'preamble'
                        section_content = []
                    section_content.append(line)
        
        # Save last section
        if current_section and section_content:
            sections[current_section]['content_lines'] = section_content
            sections[current_section]['raw_content'] = '\n'.join(section_content)
            sections[current_section]['section_type'] = self._classify_section_type(
                sections[current_section]['title'], section_content
            )
        
        self.logger.info(f"Detected {len(sections)} sections: {list(sections.keys())}")
        return sections
    
    def _match_section_pattern(self, line: str) -> Optional[Dict[str, Any]]:
        """Check if line matches any section header pattern"""
        for pattern in self.section_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return {
                        'section_number': groups[0],
                        'clean_title': groups[1].strip(),
                        'original_line': line
                    }
                elif len(groups) == 1:
                    return {
                        'section_number': None,
                        'clean_title': groups[0].strip(),
                        'original_line': line
                    }
        
        # Check for implicit section headers (standalone lines that look like titles)
        if self._looks_like_section_header(line):
            return {
                'section_number': None,
                'clean_title': line.strip(),
                'original_line': line
            }
        
        return None
    
    def _looks_like_section_header(self, line: str) -> bool:
        """Determine if a line looks like a section header"""
        line = line.strip()
        
        # Skip if too long or too short
        if len(line) < 3 or len(line) > 100:
            return False
        
        # Check for header-like patterns
        header_indicators = [
            r'^[가-힣\s]{3,30}$',  # Korean text only, moderate length
            r'^[A-Za-z\s]{3,30}$',  # English text only
            r'.*계획.*|.*방법.*|.*절차.*|.*사항.*|.*정보.*|.*내용.*',  # Common header words
        ]
        
        for pattern in header_indicators:
            if re.match(pattern, line):
                return True
        
        return False
    
    def _normalize_section_name(self, name: str) -> str:
        """Normalize section name for use as dictionary key"""
        # Remove special characters and normalize spaces
        normalized = re.sub(r'[^\w\s]', '', name)
        normalized = re.sub(r'\s+', '_', normalized.strip())
        return normalized[:50]  # Limit length
    
    def _classify_section_type(self, title: str, content_lines: List[str]) -> str:
        """Classify the type of section based on title and content"""
        title_lower = title.lower()
        content_text = '\n'.join(content_lines).lower()
        
        # Asset-related sections
        if any(keyword in title_lower for keyword in ['매각', '대상', '자산', '특허', '물건']):
            return 'asset_information'
        
        # Bidding-related sections
        if any(keyword in title_lower for keyword in ['입찰', '경매', '방법', '절차']):
            return 'bidding_procedure'
        
        # Contact/inquiry sections
        if any(keyword in title_lower for keyword in ['문의', '연락', '담당', '관재인']):
            return 'contact_information'
        
        # Legal/regulatory sections
        if any(keyword in title_lower for keyword in ['유의사항', '주의', '법적', '규정', '조건']):
            return 'legal_provisions'
        
        # Financial sections
        if any(keyword in title_lower for keyword in ['대금', '납부', '보증금', '수수료', '계약']):
            return 'financial_terms'
        
        # Schedule/timeline sections
        if any(keyword in title_lower for keyword in ['일정', '기간', '시간', '마감']):
            return 'schedule_information'
        
        # General information
        if any(keyword in title_lower for keyword in ['일반', '개요', '소개', '설명']):
            return 'general_information'
        
        # Analyze content for additional clues
        if any(indicator in content_text for indicator in ['표', 'table', '│', '┌', '├']):
            return 'tabular_data'
        
        if any(indicator in content_text for indicator in ['※', '주의', '참고', '중요']):
            return 'important_notice'
        
        return 'general_content'
    
    def _assign_content_to_sections(self, sections: Dict[str, Dict[str, Any]], 
                                   text_blocks: List[str],
                                   tables: List[Dict[str, Any]], 
                                   images: List[Dict[str, Any]]) -> Dict[str, SectionContent]:
        """Assign extracted content (tables, images) to appropriate sections"""
        sections_with_content = {}
        
        for section_key, section_info in sections.items():
            # Create section content structure
            section_content = SectionContent(
                section_name=section_info['title'],
                text_content=section_info['raw_content'],
                tables=[],
                images=[],
                subsections={},
                metadata={
                    'section_type': section_info['section_type'],
                    'start_line': section_info['start_line'],
                    'original_title': section_info.get('original_title', ''),
                    'section_number': section_info.get('section_number'),
                    'content_length': len(section_info['raw_content']),
                    'line_count': len(section_info['content_lines'])
                }
            )
            
            # Assign tables to sections based on proximity or content matching
            for table in tables:
                if self._should_assign_table_to_section(table, section_info):
                    section_content.tables.append(table)
            
            # Assign images to sections based on proximity or content matching
            for image in images:
                if self._should_assign_image_to_section(image, section_info):
                    section_content.images.append(image)
            
            # Detect and extract subsections
            subsections = self._detect_subsections(section_info['raw_content'])
            section_content.subsections = subsections
            
            # Add content analysis metadata
            section_content.metadata.update(self._analyze_section_content(section_content))
            
            sections_with_content[section_key] = section_content
        
        return sections_with_content
    
    def _should_assign_table_to_section(self, table: Dict[str, Any], 
                                       section_info: Dict[str, Any]) -> bool:
        """Determine if a table should be assigned to a specific section"""
        # Simple heuristic: assign based on page proximity
        table_page = table.get('page_number', 0)
        section_start_line = section_info.get('start_line', 0)
        
        # For now, assign all tables to all sections
        # In a more sophisticated implementation, you could use page numbers,
        # bounding box coordinates, or content analysis
        return True
    
    def _should_assign_image_to_section(self, image: Dict[str, Any], 
                                       section_info: Dict[str, Any]) -> bool:
        """Determine if an image should be assigned to a specific section"""
        # Simple heuristic similar to tables
        return True
    
    def _detect_subsections(self, content: str) -> Dict[str, SectionContent]:
        """Detect subsections within a section"""
        subsections = {}
        lines = content.split('\n')
        
        current_subsection = None
        subsection_content = []
        subsection_counter = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for subsection patterns
            subsection_match = self._match_subsection_pattern(line)
            
            if subsection_match:
                # Save previous subsection
                if current_subsection and subsection_content:
                    subsections[current_subsection] = SectionContent(
                        section_name=current_subsection,
                        text_content='\n'.join(subsection_content),
                        tables=[],
                        images=[],
                        subsections={},
                        metadata={'type': 'subsection'}
                    )
                
                # Start new subsection
                subsection_counter += 1
                subsection_name = subsection_match['title']
                subsection_key = f"subsection_{subsection_counter}_{self._normalize_section_name(subsection_name)}"
                
                current_subsection = subsection_key
                subsection_content = []
            else:
                if current_subsection:
                    subsection_content.append(line)
        
        # Save last subsection
        if current_subsection and subsection_content:
            subsections[current_subsection] = SectionContent(
                section_name=current_subsection,
                text_content='\n'.join(subsection_content),
                tables=[],
                images=[],
                subsections={},
                metadata={'type': 'subsection'}
            )
        
        return subsections
    
    def _match_subsection_pattern(self, line: str) -> Optional[Dict[str, str]]:
        """Check if line matches subsection pattern"""
        for pattern in self.subsection_patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()
                if len(groups) >= 1:
                    return {
                        'title': groups[-1].strip(),  # Last group is usually the title
                        'original_line': line
                    }
        return None
    
    def _analyze_section_content(self, section_content: SectionContent) -> Dict[str, Any]:
        """Analyze section content and extract metadata"""
        content = section_content.text_content
        analysis = {}
        
        # Count different content types
        for content_type, patterns in self.content_classifiers.items():
            count = 0
            matches = []
            for pattern in patterns:
                pattern_matches = re.findall(pattern, content, re.IGNORECASE)
                count += len(pattern_matches)
                matches.extend(pattern_matches)
            
            analysis[f"{content_type}_count"] = count
            if matches:
                analysis[f"{content_type}_samples"] = matches[:3]  # First 3 matches
        
        # Extract key information
        analysis['has_dates'] = analysis.get('dates_count', 0) > 0
        analysis['has_contact_info'] = analysis.get('contact_info_count', 0) > 0
        analysis['has_financial_info'] = analysis.get('financial_count', 0) > 0
        analysis['has_tables'] = len(section_content.tables) > 0
        analysis['has_images'] = len(section_content.images) > 0
        
        return analysis
    
    def _extract_document_metadata(self, full_text: str, file_name: str) -> Dict[str, Any]:
        """Extract document-level metadata"""
        metadata = {
            'file_name': file_name,
            'processing_timestamp': None,
            'document_type': self._identify_document_type(full_text),
            'language': 'korean',  # Assuming Korean documents
            'total_length': len(full_text),
            'total_lines': len(full_text.split('\n')),
        }
        
        # Extract title
        title = self._extract_document_title(full_text)
        if title:
            metadata['title'] = title
        
        # Extract dates
        dates = re.findall(r'\d{4}[년.-]\d{1,2}[월.-]\d{1,2}[일]?', full_text)
        if dates:
            metadata['detected_dates'] = dates[:5]  # First 5 dates
        
        # Extract organizations/contacts
        orgs = re.findall(r'(법무법인\s*[가-힣\s]+|변호사\s*[가-힣\s]+)', full_text)
        if orgs:
            metadata['organizations'] = orgs[:3]
        
        return metadata
    
    def _identify_document_type(self, text: str) -> str:
        """Identify the type of document"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['매각', '자산', '공고', '입찰']):
            return 'asset_sale_notice'
        elif any(keyword in text_lower for keyword in ['계약서', '합의서']):
            return 'contract'
        elif any(keyword in text_lower for keyword in ['공지', '안내']):
            return 'notice'
        else:
            return 'general_document'
    
    def _extract_document_title(self, text: str) -> Optional[str]:
        """Extract document title from text"""
        lines = text.split('\n')[:10]  # Check first 10 lines
        
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line) < 100:
                # Look for title patterns
                if any(keyword in line for keyword in ['공고', '매각', '자산', '특허']):
                    return line
        
        return None
    
    def _calculate_confidence(self, sections: Dict[str, SectionContent], full_text: str) -> float:
        """Calculate confidence score for the processing result"""
        confidence = 0.0
        
        # Section detection quality (40% weight)
        section_score = min(0.4, len(sections) * 0.05)  # More sections = higher confidence
        confidence += section_score
        
        # Content richness (30% weight)
        total_content_length = sum(len(section.text_content) for section in sections.values())
        content_score = min(0.3, total_content_length / 10000)  # Normalize to 10k chars
        confidence += content_score
        
        # Structured content (20% weight)
        total_tables = sum(len(section.tables) for section in sections.values())
        total_images = sum(len(section.images) for section in sections.values())
        structure_score = min(0.2, (total_tables * 0.05) + (total_images * 0.02))
        confidence += structure_score
        
        # Section type diversity (10% weight)
        section_types = set(section.metadata.get('section_type', 'unknown') for section in sections.values())
        diversity_score = min(0.1, len(section_types) * 0.02)
        confidence += diversity_score
        
        return min(1.0, confidence)
    
    def _generate_processing_notes(self, sections: Dict[str, SectionContent], 
                                  text_blocks_count: int, tables_count: int, 
                                  images_count: int) -> List[str]:
        """Generate processing notes for the result"""
        notes = []
        
        notes.append(f"Detected {len(sections)} sections dynamically")
        notes.append(f"Processed {text_blocks_count} text blocks, {tables_count} tables, {images_count} images")
        
        # Section type distribution
        section_types = {}
        for section in sections.values():
            section_type = section.metadata.get('section_type', 'unknown')
            section_types[section_type] = section_types.get(section_type, 0) + 1
        
        if section_types:
            notes.append(f"Section types: {dict(section_types)}")
        
        # Content richness analysis
        total_content = sum(len(section.text_content) for section in sections.values())
        if total_content > 5000:
            notes.append("Rich content detected (>5000 characters)")
        
        return notes
    
    def to_json_serializable(self, result: ProcessingResult) -> Dict[str, Any]:
        """Convert ProcessingResult to JSON-serializable format"""
        def convert_bbox(bbox):
            """Convert bbox to JSON-serializable format"""
            if bbox is None:
                return None
            try:
                # Handle different bbox formats
                if hasattr(bbox, '__iter__') and len(bbox) == 4:
                    return [float(x) for x in bbox]
                elif hasattr(bbox, 'x0'):  # Rect object
                    return [float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)]
                else:
                    return str(bbox)  # Fallback to string
            except:
                return None
        
        def clean_table(table):
            """Clean table data for JSON serialization"""
            cleaned = table.copy()
            if 'bbox' in cleaned:
                cleaned['bbox'] = convert_bbox(cleaned['bbox'])
            return cleaned
        
        def clean_image(image):
            """Clean image data for JSON serialization"""
            cleaned = image.copy()
            if 'bbox' in cleaned:
                cleaned['bbox'] = convert_bbox(cleaned['bbox'])
            return cleaned
        
        def section_content_to_dict(section: SectionContent) -> Dict[str, Any]:
            return {
                'section_name': section.section_name,
                'text_content': section.text_content,
                'tables': [clean_table(table) for table in section.tables],
                'images': [clean_image(image) for image in section.images],
                'subsections': {k: section_content_to_dict(v) for k, v in section.subsections.items()},
                'metadata': section.metadata
            }
        
        return {
            'success': result.success,
            'sections': {k: section_content_to_dict(v) for k, v in result.sections.items()},
            'document_metadata': result.document_metadata,
            'processing_notes': result.processing_notes,
            'confidence_score': result.confidence_score,
            'error_message': result.error_message
        }