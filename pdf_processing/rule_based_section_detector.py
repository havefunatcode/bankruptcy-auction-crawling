"""
Rule-based Section Header Detection Engine
Detects section headers using regex patterns, typography, and layout analysis
"""
import re
import statistics
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from utils.logger import setup_logger


@dataclass
class Block:
    """Represents a text block with metadata"""
    page: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    text: str
    font_size: Optional[float] = None
    is_bold: Optional[bool] = None
    line_gap_before: float = 0.0
    confidence: float = 1.0
    block_index: int = 0


@dataclass
class SectionHeader:
    """Detected section header with evidence"""
    block: Block
    header_score: float
    section_type: str
    normalized_label: str
    pattern_matched: str
    evidence: Dict[str, Any]


class RuleBasedSectionDetector:
    """Rule-based section header detection using patterns and typography"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Section header patterns (Korean legal documents)
        self.header_patterns = {
            # 번호형 (Numbered sections)
            'numbered_sections': [
                r'^(제\s*\d+\s*장)\s*(.+)',                    # 제1장 제목
                r'^(제\s*\d+\s*절)\s*(.+)',                    # 제1절 제목
                r'^(\(?[0-9]+\)?)\s*[.\)]?\s*(.+)',            # 1) 제목 or (1) 제목
                r'^(\d+(?:\.\d+)*)\s*[.\s]\s*(.+)',            # 1.1 제목 or 1.1. 제목
                r'^([IVX]+)\s*[.\)]\s*(.+)',                   # I. 제목 (로마숫자)
                r'^([가-힣])\s*[.\)]\s*(.+)',                  # 가. 제목 (한글 순번)
                r'^([가나다라마바사아자차카타파하])\s*[.\)]\s*(.+)',   # 가나다라 한글 순번
            ],
            
            # 키워드형 (Keyword-based sections)
            'keyword_sections': [
                r'^(매각\s*대상(?:\s*자산)?)\s*[:：]?\s*(.*)',           # 매각대상자산
                r'^(입찰\s*(?:방법|기간|일정|절차))\s*[:：]?\s*(.*)',      # 입찰방법/기간/일정
                r'^(입찰방법\s*[,，]\s*최저\s*입찰가?)\s*[:：]?\s*(.*)',    # 입찰방법, 최저입찰가 복합
                r'^(최저\s*입찰가?)\s*[:：]?\s*(.*)',                   # 최저입찰가
                r'^(개찰(?:\s*일시)?)\s*[:：]?\s*(.*)',                # 개찰일시
                r'^(입찰\s*보증금)\s*[:：]?\s*(.*)',                   # 입찰보증금
                r'^(입찰\s*참가\s*자격\s*및\s*방법)\s*[:：]?\s*(.*)',      # 입찰 참가 자격 및 방법
                r'^(참가\s*자격)\s*[:：]?\s*(.*)',                     # 참가자격
                r'^(계약\s*체결?\s*및\s*대금\s*납부)\s*[:：]?\s*(.*)',     # 계약체결 및 대금납부
                r'^(계약\s*체결?)\s*[:：]?\s*(.*)',                    # 계약체결
                r'^(대금\s*납부)\s*[:：]?\s*(.*)',                     # 대금납부
                r'^(유의\s*사항)\s*[:：]?\s*(.*)',                     # 유의사항
                r'^(기타\s*사항)\s*[:：]?\s*(.*)',                     # 기타사항
                r'^(문의(?:\s*처)?)\s*[:：]?\s*(.*)',                 # 문의처
                r'^(별지\s*\d+)\s*[:：]?\s*(.*)',                     # 별지1
                r'^(붙임\s*\d*)\s*[:：]?\s*(.*)',                     # 붙임1
            ],
            
            # 제목부호형 (Title with punctuation)
            'title_punctuation': [
                r'^(.+)\s*[:：]\s*$',                                 # 제목:
                r'^(.+)\s*[:：]\s*(.+)',                             # 제목: 내용
                r'^【(.+)】\s*(.*)',                                  # 【제목】
                r'^『(.+)』\s*(.*)',                                  # 『제목』
                r'^\[(.+)\]\s*(.*)',                                 # [제목]
                r'^「(.+)」\s*(.*)',                                  # 「제목」
                r'^＜(.+)＞\s*(.*)',                                  # ＜제목＞
            ],
            
            # 특수 표시형 (Special markers)
            'special_markers': [
                r'^([※▶◆★☆■□◦‣])\s*(.+)',                          # 특수문자 시작
                r'^([○●▪▫])\s*(.+)',                                # 불릿 포인트
                r'^(-{2,}|={2,}|#{2,})\s*(.+)',                      # 구분선 후 제목
            ]
        }
        
        # Section label standardization mapping
        self.label_mapping = {
            # Asset information
            '매각대상자산': 'ASSET_OVERVIEW',
            '매각대상': 'ASSET_OVERVIEW', 
            '대상자산': 'ASSET_OVERVIEW',
            '매각물건': 'ASSET_OVERVIEW',
            '특허권': 'ASSET_OVERVIEW',
            '부동산': 'ASSET_OVERVIEW',
            
            # Bidding schedule and method
            '입찰일정': 'BID_SCHEDULE',
            '입찰기간': 'BID_SCHEDULE',
            '개찰일시': 'BID_SCHEDULE',
            '입찰방법': 'BID_METHOD',
            '입찰방법, 최저 입찰가': 'BID_METHOD',
            '입찰절차': 'BID_METHOD',
            '경매방법': 'BID_METHOD',
            '입찰 참가 자격 및 방법': 'QUALIFICATION',
            
            # Qualification
            '참가자격': 'QUALIFICATION',
            '입찰자격': 'QUALIFICATION',
            '응찰자격': 'QUALIFICATION',
            
            # Contract and payment
            '계약체결': 'CONTRACT',
            '계약체결 및 대금납부': 'CONTRACT',
            '계약': 'CONTRACT',
            '낙찰': 'CONTRACT',
            '대금납부': 'PAYMENT',
            '납부방법': 'PAYMENT',
            '결제': 'PAYMENT',
            
            # Cautions and provisions
            '유의사항': 'CAUTIONS',
            '주의사항': 'CAUTIONS',
            '특기사항': 'CAUTIONS',
            '조건': 'CAUTIONS',
            
            # Contact information
            '문의처': 'CONTACT',
            '문의': 'CONTACT',
            '연락처': 'CONTACT',
            '담당자': 'CONTACT',
            
            # Appendix
            '별지': 'APPENDIX',
            '붙임': 'APPENDIX',
            '첨부': 'APPENDIX',
            '부록': 'APPENDIX',
        }
        
        # Typography scoring weights
        self.typography_weights = {
            'font_size_bonus': 0.3,
            'bold_bonus': 0.2,
            'line_gap_bonus': 0.2,
            'short_line_bonus': 0.15,
            'pattern_match_bonus': 0.4
        }
        
        # Thresholds
        self.HEADER_SCORE_THRESHOLD = 0.5  # Default threshold for digital PDFs
        self.OCR_HEADER_SCORE_THRESHOLD = 0.3  # Lower threshold for OCR/scanned PDFs
        self.MAX_HEADER_LENGTH = 200  # Increased to handle longer composite headers  
        self.MIN_HEADER_LENGTH = 3
        
    def detect_section_headers(self, blocks: List[Block], is_scanned_pdf: bool = False) -> List[SectionHeader]:
        """
        Detect section headers from text blocks
        
        Args:
            blocks: List of text blocks with metadata
            is_scanned_pdf: Whether this is a scanned PDF requiring OCR processing
            
        Returns:
            List of detected section headers
        """
        self.logger.info(f"Detecting section headers from {len(blocks)} blocks (scanned: {is_scanned_pdf})")
        
        # Use appropriate threshold based on PDF type
        threshold = self.OCR_HEADER_SCORE_THRESHOLD if is_scanned_pdf else self.HEADER_SCORE_THRESHOLD
        self.logger.info(f"Using threshold: {threshold:.2f} for {'scanned' if is_scanned_pdf else 'digital'} PDF")
        
        # Calculate baseline metrics for comparison
        baseline_metrics = self._calculate_baseline_metrics(blocks)
        
        headers = []
        
        for i, block in enumerate(blocks):
            # Skip empty or very short blocks
            text = block.text.strip()
            if len(text) < self.MIN_HEADER_LENGTH or len(text) > self.MAX_HEADER_LENGTH:
                continue
            
            # Calculate header score
            header_score, evidence = self._calculate_header_score(
                block, baseline_metrics, i, blocks
            )
            
            # Check if score exceeds threshold (using dynamic threshold)
            if header_score >= threshold:
                # Determine section type and label
                section_type, normalized_label, pattern_matched = self._classify_header(text)
                
                header = SectionHeader(
                    block=block,
                    header_score=header_score,
                    section_type=section_type,
                    normalized_label=normalized_label,
                    pattern_matched=pattern_matched,
                    evidence=evidence
                )
                
                headers.append(header)
                
                self.logger.debug(f"Header detected: '{text[:50]}...' (score: {header_score:.2f})")
            else:
                # Log near-misses for debugging
                if header_score >= threshold * 0.8:
                    self.logger.debug(f"Near-miss header: '{text[:30]}...' (score: {header_score:.2f}, threshold: {threshold:.2f})")
        
        self.logger.info(f"Detected {len(headers)} section headers using threshold {threshold:.2f}")
        return headers
    
    def _calculate_baseline_metrics(self, blocks: List[Block]) -> Dict[str, float]:
        """Calculate baseline metrics for comparison"""
        font_sizes = [b.font_size for b in blocks if b.font_size]
        line_gaps = [b.line_gap_before for b in blocks]
        text_lengths = [len(b.text.strip()) for b in blocks]
        
        return {
            'avg_font_size': statistics.mean(font_sizes) if font_sizes else 12.0,
            'avg_line_gap': statistics.mean(line_gaps) if line_gaps else 0.0,
            'avg_text_length': statistics.mean(text_lengths) if text_lengths else 50.0
        }
    
    def _calculate_header_score(self, block: Block, baseline: Dict[str, float], 
                               index: int, all_blocks: List[Block]) -> Tuple[float, Dict[str, Any]]:
        """Calculate header score for a block"""
        score = 0.0
        evidence = {}
        
        text = block.text.strip()
        
        # 1. Pattern matching score
        pattern_score, matched_pattern = self._check_header_patterns(text)
        score += pattern_score * self.typography_weights['pattern_match_bonus']
        evidence['pattern_match'] = {'score': pattern_score, 'pattern': matched_pattern}
        
        # 2. Font size score
        if block.font_size and baseline['avg_font_size'] > 0:
            font_ratio = block.font_size / baseline['avg_font_size']
            if font_ratio >= 1.2:  # 20% larger than average
                font_score = min(1.0, (font_ratio - 1.0) * 2)
                score += font_score * self.typography_weights['font_size_bonus']
                evidence['font_size'] = {'ratio': font_ratio, 'score': font_score}
        
        # 3. Bold text bonus
        if block.is_bold:
            score += self.typography_weights['bold_bonus']
            evidence['is_bold'] = True
        
        # 4. Line gap bonus (significant gap before this block)
        if block.line_gap_before > baseline['avg_line_gap'] * 1.5:
            gap_score = min(1.0, block.line_gap_before / (baseline['avg_line_gap'] * 2))
            score += gap_score * self.typography_weights['line_gap_bonus']
            evidence['line_gap'] = {'gap': block.line_gap_before, 'score': gap_score}
        
        # 5. Short line bonus (headers are typically shorter)
        if len(text) < baseline['avg_text_length'] * 0.5:
            short_score = 1.0 - (len(text) / baseline['avg_text_length'])
            score += short_score * self.typography_weights['short_line_bonus']
            evidence['short_line'] = {'length': len(text), 'score': short_score}
        
        # 6. Position context (headers often have more spacing around them)
        context_score = self._analyze_position_context(index, all_blocks)
        score += context_score * 0.1
        evidence['position_context'] = context_score
        
        return min(1.0, score), evidence
    
    def _check_header_patterns(self, text: str) -> Tuple[float, str]:
        """Check if text matches header patterns"""
        for pattern_type, patterns in self.header_patterns.items():
            for pattern in patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    # Higher score for more specific patterns
                    if pattern_type == 'keyword_sections':
                        return 1.0, pattern
                    elif pattern_type == 'numbered_sections':
                        return 0.9, pattern
                    elif pattern_type == 'title_punctuation':
                        return 0.7, pattern
                    else:
                        return 0.6, pattern
        
        # Check for implicit header characteristics
        if self._looks_like_implicit_header(text):
            return 0.5, 'implicit_header'
        
        return 0.0, 'no_match'
    
    def _looks_like_implicit_header(self, text: str) -> bool:
        """Check for implicit header characteristics"""
        # Korean title-like patterns (extended range for compound headers)
        if re.match(r'^[가-힣\s]{3,50}$', text):
            return True
        
        # Numbered section patterns
        if re.match(r'^\d+\s*\.\s*[가-힣\s,，]+', text):
            return True
            
        # Sub-section patterns (가. 나. 다.)
        if re.match(r'^[가나다라마바사아자차카타파하]\s*\.\s*[가-힣\s]+', text):
            return True
        
        # Common header words (expanded list)
        header_keywords = [
            '계획', '방법', '절차', '사항', '정보', '내용', '개요', '안내',
            '일정', '기간', '조건', '기준', '현황', '상세', '세부', '매각',
            '입찰', '자산', '대상', '공고', '자격', '참가', '계약', '체결',
            '대금', '납부', '유의', '주의', '문의', '연락', '담당'
        ]
        
        if any(keyword in text for keyword in header_keywords):
            return True
        
        # Ends with colon or similar
        if re.search(r'[:：]$', text):
            return True
            
        # Table headers (순번, 등록번호, 명칭 등)
        table_headers = ['순번', '등록번호', '명칭', '출원일', '등록일', '비고', 
                        '회차', '최저입찰가', '입찰보증금', '개찰일시']
        if any(header in text for header in table_headers):
            return True
        
        return False
    
    def _analyze_position_context(self, index: int, blocks: List[Block]) -> float:
        """Analyze surrounding context for header likelihood"""
        score = 0.0
        
        # Check spacing before and after
        if index > 0:
            prev_block = blocks[index - 1]
            current_block = blocks[index]
            
            # Large gap before suggests header
            if current_block.line_gap_before > 10:
                score += 0.5
        
        if index < len(blocks) - 1:
            next_block = blocks[index + 1]
            current_block = blocks[index]
            
            # If next block has normal gap, this might be a header
            if next_block.line_gap_before < current_block.line_gap_before:
                score += 0.3
        
        return min(1.0, score)
    
    def _classify_header(self, text: str) -> Tuple[str, str, str]:
        """Classify header and normalize label"""
        text_lower = text.lower().strip()
        
        # Try exact mapping first
        for key, label in self.label_mapping.items():
            if key in text_lower:
                return self._get_section_type(label), label, f"keyword_match_{key}"
        
        # Pattern-based classification
        if any(keyword in text_lower for keyword in ['매각', '대상', '자산', '특허', '물건']):
            return 'asset', 'ASSET_OVERVIEW', 'pattern_asset'
        elif any(keyword in text_lower for keyword in ['입찰', '경매', '개찰', '응찰']):
            return 'bidding', 'BID_METHOD', 'pattern_bidding'
        elif any(keyword in text_lower for keyword in ['자격', '조건', '요건']):
            return 'qualification', 'QUALIFICATION', 'pattern_qualification'
        elif any(keyword in text_lower for keyword in ['계약', '낙찰', '체결']):
            return 'contract', 'CONTRACT', 'pattern_contract'
        elif any(keyword in text_lower for keyword in ['대금', '납부', '결제', '보증금']):
            return 'payment', 'PAYMENT', 'pattern_payment'
        elif any(keyword in text_lower for keyword in ['유의', '주의', '특기', '조건']):
            return 'cautions', 'CAUTIONS', 'pattern_cautions'
        elif any(keyword in text_lower for keyword in ['문의', '연락', '담당', '관재인']):
            return 'contact', 'CONTACT', 'pattern_contact'
        elif any(keyword in text_lower for keyword in ['별지', '붙임', '첨부', '부록']):
            return 'appendix', 'APPENDIX', 'pattern_appendix'
        
        return 'unknown', 'UNKNOWN', 'no_classification'
    
    def _get_section_type(self, label: str) -> str:
        """Get section type from standardized label"""
        type_mapping = {
            'ASSET_OVERVIEW': 'asset',
            'BID_SCHEDULE': 'bidding',
            'BID_METHOD': 'bidding',
            'QUALIFICATION': 'qualification',
            'CONTRACT': 'contract',
            'PAYMENT': 'payment',
            'CAUTIONS': 'cautions',
            'CONTACT': 'contact',
            'APPENDIX': 'appendix'
        }
        return type_mapping.get(label, 'unknown')


def test_section_detection():
    """Test section detection with sample Korean text"""
    detector = RuleBasedSectionDetector()
    
    # Sample Korean legal document blocks
    sample_blocks = [
        Block(1, (0, 100, 500, 120), "자산매각공고", font_size=16.0, is_bold=True, line_gap_before=20.0),
        Block(1, (0, 140, 500, 160), "본 법원은 아래와 같이 자산을 매각합니다.", font_size=12.0),
        Block(1, (0, 180, 500, 200), "1. 매각대상자산", font_size=14.0, is_bold=True, line_gap_before=15.0),
        Block(1, (0, 220, 500, 240), "특허권 제1234567호", font_size=12.0),
        Block(1, (0, 260, 500, 280), "2. 입찰방법", font_size=14.0, is_bold=True, line_gap_before=15.0),
        Block(1, (0, 300, 500, 320), "서면입찰에 의합니다.", font_size=12.0),
        Block(1, (0, 340, 500, 360), "※ 유의사항", font_size=13.0, is_bold=True, line_gap_before=20.0),
        Block(1, (0, 380, 500, 400), "입찰 시 다음 사항을 유의하시기 바랍니다.", font_size=12.0),
    ]
    
    headers = detector.detect_section_headers(sample_blocks, is_scanned_pdf=False)
    
    print(f"Detected {len(headers)} headers:")
    for header in headers:
        print(f"- '{header.block.text}' -> {header.normalized_label} (score: {header.header_score:.2f})")


if __name__ == "__main__":
    test_section_detection()