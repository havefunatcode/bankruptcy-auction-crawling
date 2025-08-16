"""
Section Boundary Management System
Handles section boundary confirmation, merging, and cross-page continuity
"""
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from .rule_based_section_detector import Block, SectionHeader
from utils.logger import setup_logger


@dataclass
class Section:
    """Represents a complete section with boundaries"""
    header: SectionHeader
    start_block_index: int
    end_block_index: int
    content_blocks: List[Block]
    section_id: str
    confidence: float
    merge_history: List[str]
    cross_page_continuation: bool = False


@dataclass
class TableContinuation:
    """Information about table continuation across pages"""
    is_continuation: bool
    original_table_page: int
    header_match_score: float
    continuation_evidence: List[str]


class SectionBoundaryManager:
    """Manages section boundaries, merging, and continuity"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Merging configuration
        self.MIN_SECTION_LENGTH = 30  # Minimum characters for a section
        self.MIN_BLOCKS_PER_SECTION = 2  # Minimum blocks per section
        self.MERGE_SIMILARITY_THRESHOLD = 0.7
        
        # Cross-page continuation patterns
        self.continuation_patterns = {
            'sentence_continuation': [
                r'[,，]\s*$',      # Ends with comma
                r'[-－]\s*$',      # Ends with dash
                r'다음과\s*같음?\s*[:：]?\s*$',  # "다음과 같음:"
                r'아래와?\s*같음?\s*[:：]?\s*$',  # "아래와 같음:"
                r'하기와?\s*같음?\s*[:：]?\s*$',  # "하기와 같음:"
                r'기재와?\s*같음?\s*[:：]?\s*$',  # "기재와 같음:"
            ],
            'table_continuation': [
                r'\(계속\)\s*$',   # "(계속)"
                r'\(다음\s*페이지\s*계속\)',  # "(다음페이지 계속)"
                r'표\s*계속',      # "표 계속"
                r'〈계속〉',        # "〈계속〉"
            ],
            'list_continuation': [
                r'^\s*[0-9]+\s*[.)\)]',    # Numbered list continues
                r'^\s*[가-힣]\s*[.)\)]',   # Korean lettered list continues
                r'^\s*[-·‧•]\s*',          # Bullet list continues
            ]
        }
        
        # Table header similarity patterns
        self.table_header_patterns = [
            r'순\s*번',  # 순번
            r'번\s*호',  # 번호
            r'구\s*분',  # 구분
            r'내\s*용',  # 내용
            r'금\s*액',  # 금액
            r'비\s*고',  # 비고
            r'특허\s*번호', # 특허번호
            r'등록\s*번호', # 등록번호
        ]
    
    def determine_section_boundaries(self, headers: List[SectionHeader], 
                                   all_blocks: List[Block]) -> List[Section]:
        """
        Determine section boundaries from detected headers
        
        Args:
            headers: List of detected section headers
            all_blocks: All text blocks in the document
            
        Returns:
            List of sections with confirmed boundaries
        """
        self.logger.info(f"Determining boundaries for {len(headers)} headers across {len(all_blocks)} blocks")
        
        # Sort headers by position
        sorted_headers = sorted(headers, key=lambda h: (h.block.page, h.block.bbox[1]))
        
        # Create initial sections
        sections = []
        for i, header in enumerate(sorted_headers):
            # Find header position in blocks
            header_block_index = self._find_block_index(header.block, all_blocks)
            
            if header_block_index == -1:
                continue
            
            # Determine section end
            if i < len(sorted_headers) - 1:
                next_header = sorted_headers[i + 1]
                next_header_index = self._find_block_index(next_header.block, all_blocks)
                end_index = next_header_index - 1 if next_header_index > header_block_index else len(all_blocks) - 1
            else:
                end_index = len(all_blocks) - 1
            
            # Extract content blocks (include more blocks after header for table content)
            start_content_index = header_block_index + 1
            
            # Extend section boundaries to capture tables
            extended_end_index = self._extend_section_for_tables(
                header_block_index, end_index, all_blocks
            )
            
            content_blocks = all_blocks[start_content_index:extended_end_index + 1]
            
            # Create section
            section = Section(
                header=header,
                start_block_index=header_block_index,
                end_block_index=end_index,
                content_blocks=content_blocks,
                section_id=f"section_{i+1}_{header.normalized_label}",
                confidence=header.header_score,
                merge_history=[],
                cross_page_continuation=False
            )
            
            sections.append(section)
        
        # Handle cross-page continuations
        sections = self._handle_cross_page_continuations(sections, all_blocks)
        
        # Merge short sections
        sections = self._merge_short_sections(sections)
        
        # Handle table continuations
        sections = self._handle_table_continuations(sections, all_blocks)
        
        self.logger.info(f"Finalized {len(sections)} sections with boundaries")
        return sections
    
    def _find_block_index(self, target_block: Block, all_blocks: List[Block]) -> int:
        """Find the index of a block in the list"""
        for i, block in enumerate(all_blocks):
            if (block.page == target_block.page and 
                block.bbox == target_block.bbox and 
                block.text == target_block.text):
                return i
        return -1
    
    def _handle_cross_page_continuations(self, sections: List[Section], 
                                       all_blocks: List[Block]) -> List[Section]:
        """Handle sections that continue across pages"""
        for section in sections:
            if not section.content_blocks:
                continue
            
            last_block = section.content_blocks[-1]
            last_text = last_block.text.strip()
            
            # Check for continuation patterns
            is_continuation = False
            continuation_type = None
            
            for pattern_type, patterns in self.continuation_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, last_text):
                        is_continuation = True
                        continuation_type = pattern_type
                        break
                if is_continuation:
                    break
            
            if is_continuation:
                # Try to extend section to next page
                extended_blocks = self._extend_to_next_page(
                    section, all_blocks, continuation_type
                )
                
                if extended_blocks:
                    section.content_blocks.extend(extended_blocks)
                    section.end_block_index += len(extended_blocks)
                    section.cross_page_continuation = True
                    section.merge_history.append(f"cross_page_extension_{continuation_type}")
                    
                    self.logger.debug(f"Extended section '{section.section_id}' across pages")
        
        return sections
    
    def _extend_to_next_page(self, section: Section, all_blocks: List[Block], 
                           continuation_type: str) -> List[Block]:
        """Extend section to next page based on continuation type"""
        if not section.content_blocks:
            return []
        
        last_block = section.content_blocks[-1]
        current_page = last_block.page
        
        # Find blocks on next page
        next_page_blocks = [b for b in all_blocks if b.page == current_page + 1]
        
        if not next_page_blocks:
            return []
        
        # Different strategies based on continuation type
        if continuation_type == 'sentence_continuation':
            # Take blocks until we find a natural break
            extended_blocks = []
            for block in next_page_blocks:
                extended_blocks.append(block)
                # Stop at sentence end or new header-like pattern
                if (re.search(r'[.!?。！？]\s*$', block.text) or 
                    self._looks_like_new_section_start(block.text)):
                    break
                # Don't extend too far
                if len(extended_blocks) >= 5:
                    break
            return extended_blocks
        
        elif continuation_type == 'table_continuation':
            # Take blocks that look like table rows
            return self._extract_continued_table_blocks(next_page_blocks)
        
        elif continuation_type == 'list_continuation':
            # Take blocks that continue the list pattern
            return self._extract_continued_list_blocks(next_page_blocks, section)
        
        return []
    
    def _looks_like_new_section_start(self, text: str) -> bool:
        """Check if text looks like the start of a new section"""
        # Check for typical header patterns
        header_patterns = [
            r'^\d+\s*[.)\]]',        # 1. or 1) or 1]
            r'^[가-힣]\s*[.)\]]',    # 가. or 가) or 가]
            r'^[IVX]+\s*[.)\]]',     # I. or I) or I]
            r'^(매각|입찰|계약|대금|유의|문의)',  # Common section keywords
        ]
        
        for pattern in header_patterns:
            if re.match(pattern, text.strip()):
                return True
        
        return False
    
    def _extract_continued_table_blocks(self, blocks: List[Block]) -> List[Block]:
        """Extract blocks that appear to be table continuation"""
        table_blocks = []
        
        for block in blocks:
            text = block.text.strip()
            
            # Check for table-like characteristics
            if (self._has_table_structure(text) or 
                any(pattern in text for pattern in ['│', '┌', '├', '└', '┐', '┤', '┘'])):
                table_blocks.append(block)
            else:
                # Stop if we hit non-table content
                break
        
        return table_blocks
    
    def _extract_continued_list_blocks(self, blocks: List[Block], 
                                     original_section: Section) -> List[Block]:
        """Extract blocks that continue a list pattern"""
        list_blocks = []
        
        # Analyze original section to understand list pattern
        list_pattern = self._detect_list_pattern(original_section.content_blocks)
        
        for block in blocks:
            text = block.text.strip()
            
            if self._matches_list_pattern(text, list_pattern):
                list_blocks.append(block)
            else:
                break
        
        return list_blocks
    
    def _has_table_structure(self, text: str) -> bool:
        """Check if text has table-like structure"""
        # Multiple spaces (table columns)
        if re.search(r'\s{3,}', text):
            return True
        
        # Tab characters
        if '\t' in text:
            return True
        
        # Numbers and units pattern (common in tables)
        if re.search(r'\d+[,.]?\d*\s*(원|개|건|명|%)', text):
            return True
        
        return False
    
    def _detect_list_pattern(self, blocks: List[Block]) -> Optional[str]:
        """Detect the list pattern used in blocks"""
        for block in blocks:
            text = block.text.strip()
            
            # Check for various list patterns
            if re.match(r'^\s*\d+\s*[.)\)]', text):
                return 'numbered'
            elif re.match(r'^\s*[가-힣]\s*[.)\)]', text):
                return 'korean_lettered'
            elif re.match(r'^\s*[-·‧•]\s*', text):
                return 'bullet'
        
        return None
    
    def _matches_list_pattern(self, text: str, pattern: Optional[str]) -> bool:
        """Check if text matches the detected list pattern"""
        if not pattern:
            return False
        
        if pattern == 'numbered':
            return bool(re.match(r'^\s*\d+\s*[.)\)]', text))
        elif pattern == 'korean_lettered':
            return bool(re.match(r'^\s*[가-힣]\s*[.)\)]', text))
        elif pattern == 'bullet':
            return bool(re.match(r'^\s*[-·‧•]\s*', text))
        
        return False
    
    def _merge_short_sections(self, sections: List[Section]) -> List[Section]:
        """Merge sections that are too short"""
        merged_sections = []
        i = 0
        
        while i < len(sections):
            current_section = sections[i]
            
            # Check if current section is too short
            if self._is_section_too_short(current_section):
                # Try to merge with adjacent section
                merge_target = self._find_merge_target(current_section, sections, i)
                
                if merge_target is not None:
                    merged_section = self._merge_sections(current_section, sections[merge_target])
                    
                    # Replace both sections with merged section
                    if merge_target < i:
                        merged_sections[-1] = merged_section  # Replace previous section
                        i += 1  # Skip current section
                    else:
                        merged_sections.append(merged_section)
                        i += 2  # Skip both current and next section
                    
                    continue
            
            merged_sections.append(current_section)
            i += 1
        
        return merged_sections
    
    def _is_section_too_short(self, section: Section) -> bool:
        """Check if section is too short to stand alone"""
        total_chars = sum(len(block.text) for block in section.content_blocks)
        
        return (total_chars < self.MIN_SECTION_LENGTH or 
                len(section.content_blocks) < self.MIN_BLOCKS_PER_SECTION)
    
    def _find_merge_target(self, section: Section, all_sections: List[Section], 
                          current_index: int) -> Optional[int]:
        """Find the best section to merge with"""
        # Check previous section
        if current_index > 0:
            prev_section = all_sections[current_index - 1]
            if self._can_merge_sections(section, prev_section):
                return current_index - 1
        
        # Check next section
        if current_index < len(all_sections) - 1:
            next_section = all_sections[current_index + 1]
            if self._can_merge_sections(section, next_section):
                return current_index + 1
        
        return None
    
    def _can_merge_sections(self, section1: Section, section2: Section) -> bool:
        """Check if two sections can be merged"""
        # Same section type
        if section1.header.section_type == section2.header.section_type:
            return True
        
        # Both are unknown type
        if (section1.header.normalized_label == 'UNKNOWN' and 
            section2.header.normalized_label == 'UNKNOWN'):
            return True
        
        return False
    
    def _merge_sections(self, section1: Section, section2: Section) -> Section:
        """Merge two sections"""
        # Use the section with higher confidence as primary
        if section1.confidence >= section2.confidence:
            primary, secondary = section1, section2
        else:
            primary, secondary = section2, section1
        
        # Combine content blocks
        all_blocks = primary.content_blocks + secondary.content_blocks
        
        # Create merged section
        merged_section = Section(
            header=primary.header,
            start_block_index=min(primary.start_block_index, secondary.start_block_index),
            end_block_index=max(primary.end_block_index, secondary.end_block_index),
            content_blocks=all_blocks,
            section_id=f"{primary.section_id}_merged_with_{secondary.section_id}",
            confidence=(primary.confidence + secondary.confidence) / 2,
            merge_history=primary.merge_history + secondary.merge_history + ['section_merge'],
            cross_page_continuation=primary.cross_page_continuation or secondary.cross_page_continuation
        )
        
        return merged_section
    
    def _handle_table_continuations(self, sections: List[Section], 
                                  all_blocks: List[Block]) -> List[Section]:
        """Handle table continuations across pages"""
        for section in sections:
            if not section.content_blocks:
                continue
            
            # Check if section contains tables that might continue
            table_continuation = self._detect_table_continuation(section, all_blocks)
            
            if table_continuation.is_continuation:
                section.merge_history.append(f"table_continuation_detected")
                # Additional processing could be added here
        
        return sections
    
    def _detect_table_continuation(self, section: Section, 
                                 all_blocks: List[Block]) -> TableContinuation:
        """Detect if section contains table continuation"""
        # Look for table header patterns in section content
        header_matches = 0
        total_blocks = len(section.content_blocks)
        
        if total_blocks == 0:
            return TableContinuation(False, 0, 0.0, [])
        
        for block in section.content_blocks[:3]:  # Check first few blocks
            for pattern in self.table_header_patterns:
                if re.search(pattern, block.text):
                    header_matches += 1
                    break
        
        header_match_score = header_matches / min(3, total_blocks)
        
        # Check for continuation indicators
        evidence = []
        for block in section.content_blocks:
            for pattern_type, patterns in self.continuation_patterns.items():
                if pattern_type == 'table_continuation':
                    for pattern in patterns:
                        if re.search(pattern, block.text):
                            evidence.append(f"found_{pattern}")
        
        is_continuation = header_match_score > 0.3 or len(evidence) > 0
        
        return TableContinuation(
            is_continuation=is_continuation,
            original_table_page=section.content_blocks[0].page if section.content_blocks else 0,
            header_match_score=header_match_score,
            continuation_evidence=evidence
        )
    
    def _extend_section_for_tables(self, header_index: int, original_end_index: int, 
                                 all_blocks: List[Block]) -> int:
        """Extend section boundaries to include complete tables"""
        current_end = original_end_index
        
        # Check if the section contains table-like content
        table_detected = False
        for i in range(header_index + 1, min(header_index + 10, len(all_blocks))):
            if i >= len(all_blocks):
                break
            block = all_blocks[i]
            
            # Look for table indicators
            if (self._has_table_structure(block.text) or 
                any(header in block.text for header in ['순번', '등록번호', '명칭', '회차', '최저입찰가'])):
                table_detected = True
                break
        
        if not table_detected:
            return original_end_index
        
        # If table detected, extend to capture all table content
        extended_end = original_end_index
        
        # Look ahead for table continuation
        for i in range(original_end_index + 1, min(original_end_index + 20, len(all_blocks))):
            if i >= len(all_blocks):
                break
                
            block = all_blocks[i]
            text = block.text.strip()
            
            # Stop if we hit a clear section header
            if self._is_clear_section_header(text):
                break
            
            # Continue if looks like table content
            if (self._has_table_structure(text) or 
                re.match(r'^\s*\d+\s+', text) or  # Table row starting with number
                len(text.split()) > 3):  # Multi-column content
                extended_end = i
            else:
                # Stop extending if we hit content that doesn't look like table
                if len(text) > 50 and not self._has_table_structure(text):
                    break
        
        if extended_end > original_end_index:
            self.logger.debug(f"Extended section boundary from {original_end_index} to {extended_end} for table content")
        
        return extended_end
    
    def _is_clear_section_header(self, text: str) -> bool:
        """Check if text is clearly a section header"""
        # Strong header patterns
        strong_patterns = [
            r'^\d+\s*\.\s*[가-힣\s]+',  # "1. 매각대상자산"
            r'^[가나다라마바사]\s*\.\s*[가-힣\s]+',  # "가. 입찰방법"
            r'^\d+\s*\.\s*[가-힣\s,，]+',  # "2. 입찰방법, 최저 입찰가"
        ]
        
        for pattern in strong_patterns:
            if re.match(pattern, text):
                return True
        
        # Section keywords at the start
        section_keywords = ['매각대상', '입찰방법', '입찰일정', '참가자격', '계약체결', '유의사항', '문의처', '기타사항']
        text_clean = text.lower().strip()
        
        if any(text_clean.startswith(keyword) for keyword in section_keywords):
            return True
        
        return False