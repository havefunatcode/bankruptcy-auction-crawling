"""
Content Type Classification System
Classifies section content into TABLE, LIST, PARAGRAPH, or MIXED types
"""
import re
import statistics
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from .section_boundary_manager import Block, Section
from utils.logger import setup_logger


@dataclass
class ContentAnalysis:
    """Analysis result for content classification"""
    content_type: str  # TABLE, LIST, PARAGRAPH, MIXED
    confidence: float
    characteristics: Dict[str, Any]
    evidence: List[str]
    sub_types: List[str]


@dataclass
class TableStructure:
    """Detected table structure information"""
    has_headers: bool
    column_count: int
    row_count: int
    delimiter_type: str  # 'tab', 'space', 'pipe', 'line'
    alignment_score: float
    column_headers: List[str]


class ContentTypeClassifier:
    """Classifies content types using rule-based analysis"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Content type patterns
        self.table_indicators = {
            'structural': [
                r'\t',                    # Tab characters
                r'\s{3,}',               # Multiple spaces (3+)
                r'[│┌├└┐┤┘┬┴┼]',        # Box drawing characters
                r'\|.*\|',               # Pipe delimited
                r'─{2,}',                # Horizontal lines
                r'━{2,}',                # Double horizontal lines
            ],
            'content': [
                r'\d+[,.]?\d*\s*(원|개|건|명|%|kg|m²|㎡)',  # Numbers with units
                r'(\d{1,3}[,]\d{3})+',   # Formatted numbers
                r'\d+\.\d+%',            # Percentages
                r'\d{4}[-.]?\d{2}[-.]?\d{2}',  # Dates
            ],
            'headers': [
                r'순\s*번|번\s*호|구\s*분|내\s*용|금\s*액|비\s*고',  # Common table headers
                r'특허\s*번호|등록\s*번호|출원\s*번호',
                r'면\s*적|위\s*치|용\s*도|구\s*조',
            ]
        }
        
        self.list_indicators = {
            'bullets': [
                r'^\s*[-·‧•◦▪▫■□◆◇○●]\s+',  # Various bullet points
                r'^\s*[※▶◆★☆]\s+',          # Special markers
            ],
            'numbered': [
                r'^\s*\d+\s*[.)\]]\s+',      # 1. or 1) or 1]
                r'^\s*\(\d+\)\s+',           # (1)
                r'^\s*\d+\s*-\s*',           # 1-
            ],
            'lettered': [
                r'^\s*[가-힣]\s*[.)\]]\s+',  # 가. or 가) or 가]
                r'^\s*\([가-힣]\)\s+',       # (가)
                r'^\s*[a-zA-Z]\s*[.)\]]\s+', # a. or a) or a]
                r'^\s*\([a-zA-Z]\)\s+',      # (a)
            ],
            'roman': [
                r'^\s*[IVX]+\s*[.)\]]\s+',   # I. or I) or I]
                r'^\s*\([IVX]+\)\s+',        # (I)
            ]
        }
        
        self.paragraph_indicators = {
            'korean_text': [
                r'[가-힣]{10,}',             # Long Korean text
                r'[다고니까에를이의은는을를]\s',  # Korean particles
                r'[습니다입니다였습니다했습니다]\s*[.。]',  # Korean endings
            ],
            'sentence_structure': [
                r'[.!?。！？]\s+[A-Z가-힣]',   # Sentence breaks
                r'[,，]\s+',                  # Comma usage
                r'[:：]\s*',                  # Colon usage
            ],
            'continuous_text': [
                r'.{50,}',                    # Long continuous text
                r'\S+\s+\S+\s+\S+',          # Multiple words
            ]
        }
        
        # Classification thresholds
        self.TABLE_THRESHOLD = 0.6
        self.LIST_THRESHOLD = 0.5
        self.PARAGRAPH_THRESHOLD = 0.4
        self.MIXED_THRESHOLD = 0.3
        
    def classify_section_content(self, section: Section) -> ContentAnalysis:
        """
        Classify the content type of a section
        
        Args:
            section: Section to classify
            
        Returns:
            ContentAnalysis with classification result
        """
        if not section.content_blocks:
            return ContentAnalysis(
                content_type='EMPTY',
                confidence=1.0,
                characteristics={'block_count': 0},
                evidence=['no_content_blocks'],
                sub_types=[]
            )
        
        # Combine all text from content blocks
        combined_text = '\n'.join(block.text for block in section.content_blocks)
        
        # Calculate scores for each content type
        table_score, table_evidence = self._calculate_table_score(section.content_blocks, combined_text)
        list_score, list_evidence = self._calculate_list_score(section.content_blocks, combined_text)
        paragraph_score, paragraph_evidence = self._calculate_paragraph_score(section.content_blocks, combined_text)
        
        # Determine primary type
        scores = {
            'TABLE': table_score,
            'LIST': list_score,
            'PARAGRAPH': paragraph_score
        }
        
        primary_type = max(scores, key=scores.get)
        primary_score = scores[primary_type]
        
        # Check for mixed content
        high_scores = [t for t, s in scores.items() if s > self.MIXED_THRESHOLD]
        is_mixed = len(high_scores) > 1
        
        if is_mixed and primary_score < 0.8:
            content_type = 'MIXED'
            confidence = min(primary_score + 0.2, 1.0)
            sub_types = sorted(high_scores, key=lambda t: scores[t], reverse=True)
        else:
            content_type = primary_type
            confidence = primary_score
            sub_types = [primary_type]
        
        # Gather all evidence
        all_evidence = table_evidence + list_evidence + paragraph_evidence
        
        # Extract detailed characteristics
        characteristics = self._extract_content_characteristics(section.content_blocks, combined_text)
        
        # Add type-specific analysis
        if content_type == 'TABLE' or 'TABLE' in sub_types:
            table_structure = self._analyze_table_structure(section.content_blocks)
            characteristics['table_structure'] = table_structure
        
        return ContentAnalysis(
            content_type=content_type,
            confidence=confidence,
            characteristics=characteristics,
            evidence=all_evidence,
            sub_types=sub_types
        )
    
    def _calculate_table_score(self, blocks: List[Block], text: str) -> Tuple[float, List[str]]:
        """Calculate score for table content type"""
        score = 0.0
        evidence = []
        
        # Check structural indicators
        for pattern in self.table_indicators['structural']:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                weight = 0.3 if pattern == r'\t' else 0.2
                score += min(weight, matches * 0.05)
                evidence.append(f"structural_pattern_{pattern[:10]}_{matches}")
        
        # Check content indicators
        for pattern in self.table_indicators['content']:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                score += min(0.2, matches * 0.03)
                evidence.append(f"content_pattern_{pattern[:15]}_{matches}")
        
        # Check header indicators
        for pattern in self.table_indicators['headers']:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                score += min(0.3, matches * 0.1)
                evidence.append(f"header_pattern_{pattern[:15]}_{matches}")
        
        # Analyze block alignment
        alignment_score = self._analyze_block_alignment(blocks)
        if alignment_score > 0.5:
            score += 0.2
            evidence.append(f"block_alignment_{alignment_score:.2f}")
        
        # Check for consistent spacing patterns
        spacing_score = self._analyze_spacing_patterns(blocks)
        if spacing_score > 0.3:
            score += 0.1
            evidence.append(f"spacing_pattern_{spacing_score:.2f}")
        
        return min(1.0, score), evidence
    
    def _calculate_list_score(self, blocks: List[Block], text: str) -> Tuple[float, List[str]]:
        """Calculate score for list content type"""
        score = 0.0
        evidence = []
        
        # Check each block for list patterns
        list_blocks = 0
        total_blocks = len(blocks)
        
        for block in blocks:
            block_text = block.text.strip()
            is_list_item = False
            
            # Check bullet patterns
            for pattern in self.list_indicators['bullets']:
                if re.match(pattern, block_text):
                    list_blocks += 1
                    is_list_item = True
                    evidence.append(f"bullet_pattern_{pattern[:10]}")
                    break
            
            if not is_list_item:
                # Check numbered patterns
                for pattern in self.list_indicators['numbered']:
                    if re.match(pattern, block_text):
                        list_blocks += 1
                        is_list_item = True
                        evidence.append(f"numbered_pattern_{pattern[:10]}")
                        break
            
            if not is_list_item:
                # Check lettered patterns
                for pattern in self.list_indicators['lettered']:
                    if re.match(pattern, block_text):
                        list_blocks += 1
                        is_list_item = True
                        evidence.append(f"lettered_pattern_{pattern[:10]}")
                        break
            
            if not is_list_item:
                # Check roman numeral patterns
                for pattern in self.list_indicators['roman']:
                    if re.match(pattern, block_text):
                        list_blocks += 1
                        is_list_item = True
                        evidence.append(f"roman_pattern_{pattern[:10]}")
                        break
        
        # Calculate score based on percentage of list blocks
        if total_blocks > 0:
            list_ratio = list_blocks / total_blocks
            score = list_ratio * 0.8  # Base score from list pattern ratio
            
            # Bonus for consistent patterns
            if list_ratio > 0.7:
                score += 0.2
                evidence.append(f"high_list_ratio_{list_ratio:.2f}")
        
        return min(1.0, score), evidence
    
    def _calculate_paragraph_score(self, blocks: List[Block], text: str) -> Tuple[float, List[str]]:
        """Calculate score for paragraph content type"""
        score = 0.0
        evidence = []
        
        # Check Korean text patterns
        for pattern in self.paragraph_indicators['korean_text']:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                score += min(0.3, matches * 0.02)
                evidence.append(f"korean_text_{pattern[:15]}_{matches}")
        
        # Check sentence structure
        for pattern in self.paragraph_indicators['sentence_structure']:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                score += min(0.2, matches * 0.01)
                evidence.append(f"sentence_structure_{pattern[:15]}_{matches}")
        
        # Check continuous text
        for pattern in self.paragraph_indicators['continuous_text']:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                score += min(0.3, matches * 0.01)
                evidence.append(f"continuous_text_{pattern[:15]}_{matches}")
        
        # Analyze text flow characteristics
        flow_score = self._analyze_text_flow(blocks)
        if flow_score > 0.3:
            score += 0.2
            evidence.append(f"text_flow_{flow_score:.2f}")
        
        # Check line length variance (paragraphs have more varied line lengths)
        variance_score = self._analyze_line_length_variance(blocks)
        if variance_score > 0.3:
            score += 0.1
            evidence.append(f"line_variance_{variance_score:.2f}")
        
        return min(1.0, score), evidence
    
    def _analyze_block_alignment(self, blocks: List[Block]) -> float:
        """Analyze alignment patterns in blocks (table indicator)"""
        if len(blocks) < 2:
            return 0.0
        
        # Check x-coordinate alignment
        x_positions = [block.bbox[0] for block in blocks]
        
        # Group by similar x positions (within 5 points)
        x_groups = {}
        for x in x_positions:
            found_group = False
            for group_x in x_groups:
                if abs(x - group_x) <= 5:
                    x_groups[group_x].append(x)
                    found_group = True
                    break
            if not found_group:
                x_groups[x] = [x]
        
        # Strong alignment if most blocks align to few positions
        if len(x_groups) <= max(2, len(blocks) // 3):
            return 0.8
        elif len(x_groups) <= len(blocks) // 2:
            return 0.5
        else:
            return 0.2
    
    def _analyze_spacing_patterns(self, blocks: List[Block]) -> float:
        """Analyze consistent spacing patterns (table indicator)"""
        if len(blocks) < 3:
            return 0.0
        
        # Analyze spaces within each block
        space_patterns = []
        for block in blocks:
            # Count sequences of spaces
            space_sequences = re.findall(r'\s{2,}', block.text)
            if space_sequences:
                space_patterns.append(len(space_sequences))
        
        if not space_patterns:
            return 0.0
        
        # Check consistency
        if len(set(space_patterns)) <= 2:  # Similar patterns
            return 0.7
        elif statistics.stdev(space_patterns) < 2:  # Low variance
            return 0.5
        else:
            return 0.2
    
    def _analyze_text_flow(self, blocks: List[Block]) -> float:
        """Analyze text flow characteristics (paragraph indicator)"""
        if len(blocks) < 2:
            return 0.0
        
        # Check for sentence continuity across blocks
        continuity_score = 0.0
        
        for i in range(len(blocks) - 1):
            current_text = blocks[i].text.strip()
            next_text = blocks[i + 1].text.strip()
            
            # Check if current block doesn't end with sentence terminator
            if not re.search(r'[.!?。！？]\s*$', current_text):
                # And next block doesn't start with list marker or number
                if not re.match(r'^\s*[\d가-힣IVX]+\s*[.)\]]', next_text):
                    continuity_score += 1
        
        return continuity_score / (len(blocks) - 1) if len(blocks) > 1 else 0.0
    
    def _analyze_line_length_variance(self, blocks: List[Block]) -> float:
        """Analyze line length variance (paragraph indicator)"""
        if len(blocks) < 3:
            return 0.0
        
        lengths = [len(block.text.strip()) for block in blocks]
        
        if len(set(lengths)) == 1:  # All same length
            return 0.0
        
        try:
            variance = statistics.stdev(lengths) / statistics.mean(lengths)
            return min(1.0, variance)
        except:
            return 0.0
    
    def _extract_content_characteristics(self, blocks: List[Block], text: str) -> Dict[str, Any]:
        """Extract detailed content characteristics"""
        characteristics = {
            'block_count': len(blocks),
            'total_length': len(text),
            'average_block_length': sum(len(b.text) for b in blocks) / len(blocks) if blocks else 0,
            'has_numbers': bool(re.search(r'\d+', text)),
            'has_korean': bool(re.search(r'[가-힣]', text)),
            'has_special_chars': bool(re.search(r'[│┌├└┐┤┘┬┴┼○●▪▫■□]', text)),
            'line_count': text.count('\n') + 1,
        }
        
        # Extract specific patterns
        characteristics['date_patterns'] = len(re.findall(r'\d{4}[-.]?\d{2}[-.]?\d{2}', text))
        characteristics['money_patterns'] = len(re.findall(r'\d+[,.]?\d*\s*원', text))
        characteristics['phone_patterns'] = len(re.findall(r'\d{2,3}-\d{3,4}-\d{4}', text))
        characteristics['email_patterns'] = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        
        return characteristics
    
    def _analyze_table_structure(self, blocks: List[Block]) -> Optional[TableStructure]:
        """Analyze table structure details"""
        if not blocks:
            return None
        
        # Combine text for analysis
        combined_text = '\n'.join(block.text for block in blocks)
        
        # Detect delimiter type
        delimiter_type = 'space'  # Default
        if '\t' in combined_text:
            delimiter_type = 'tab'
        elif '|' in combined_text:
            delimiter_type = 'pipe'
        elif re.search(r'[│┌├└┐┤┘]', combined_text):
            delimiter_type = 'line'
        
        # Estimate column count
        lines = combined_text.split('\n')
        column_counts = []
        
        for line in lines[:5]:  # Check first 5 lines
            if delimiter_type == 'tab':
                cols = len(line.split('\t'))
            elif delimiter_type == 'pipe':
                cols = len(line.split('|'))
            else:
                # Count space-separated groups
                cols = len(re.split(r'\s{2,}', line.strip()))
            
            if cols > 1:
                column_counts.append(cols)
        
        column_count = max(column_counts) if column_counts else 1
        row_count = len([line for line in lines if line.strip()])
        
        # Check for headers
        has_headers = any(
            re.search(pattern, combined_text, re.IGNORECASE)
            for pattern in self.table_indicators['headers']
        )
        
        # Extract potential column headers
        column_headers = []
        if has_headers and lines:
            first_line = lines[0]
            if delimiter_type == 'tab':
                column_headers = first_line.split('\t')
            elif delimiter_type == 'pipe':
                column_headers = [col.strip() for col in first_line.split('|') if col.strip()]
            else:
                column_headers = re.split(r'\s{2,}', first_line.strip())
        
        # Calculate alignment score
        alignment_score = self._analyze_block_alignment(blocks)
        
        return TableStructure(
            has_headers=has_headers,
            column_count=column_count,
            row_count=row_count,
            delimiter_type=delimiter_type,
            alignment_score=alignment_score,
            column_headers=column_headers[:5]  # Limit to first 5
        )