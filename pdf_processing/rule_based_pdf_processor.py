"""
Rule-based PDF Processor
Integrates all components for complete PDF section processing
"""
import os
import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image
import io
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import json
from pathlib import Path

from .pdf_type_detector import PDFTypeDetector, PDFTypeResult
from .rule_based_section_detector import RuleBasedSectionDetector, Block, SectionHeader
from .section_boundary_manager import SectionBoundaryManager, Section
from .content_type_classifier import ContentTypeClassifier, ContentAnalysis
from .field_normalizer import FieldNormalizer, NormalizedField
from .evidence_system import (
    EvidenceTracker, ConfidenceCalculator, ExtractedValue,
    Evidence, BoundingBox, ExtractionMethod, create_evidence_from_extraction
)
from utils.logger import setup_logger


@dataclass
class ProcessingResult:
    """Complete processing result for a PDF document"""
    success: bool
    notice_id: str
    file_name: str
    pdf_type_result: PDFTypeResult
    extracted_sections: List[Section]
    content_analyses: Dict[str, ContentAnalysis]
    normalized_fields: Dict[str, Dict[str, NormalizedField]]
    evidence_report: Dict[str, Any]
    processing_metadata: Dict[str, Any]
    error_message: Optional[str] = None


class RuleBasedPDFProcessor:
    """Rule-based PDF processor using heuristics and patterns"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Initialize components
        self.type_detector = PDFTypeDetector()
        self.section_detector = RuleBasedSectionDetector()
        self.boundary_manager = SectionBoundaryManager()
        self.content_classifier = ContentTypeClassifier()
        self.field_normalizer = FieldNormalizer()
        self.evidence_tracker = EvidenceTracker()
        self.confidence_calculator = ConfidenceCalculator()
        
        # Processing configuration
        self.max_pages_to_analyze = 50  # Limit for very large documents
        self.ocr_config = '--oem 1 --psm 4 -l kor+eng'
        self.image_dpi = 300
        
    def process_pdf(self, pdf_path: str, notice_id: str) -> ProcessingResult:
        """
        Process PDF using rule-based approach
        
        Args:
            pdf_path: Path to PDF file
            notice_id: Notice identifier
            
        Returns:
            ProcessingResult with all extracted data
        """
        try:
            self.logger.info(f"Starting rule-based processing of {pdf_path}")
            file_name = os.path.basename(pdf_path)
            
            # Reset evidence tracker for new document
            self.evidence_tracker = EvidenceTracker()
            
            # Step 1: Detect PDF type
            pdf_type_result = self.type_detector.detect_pdf_type(pdf_path)
            self.logger.info(f"PDF type: {'Digital' if pdf_type_result.is_digital else 'Scanned'} "
                           f"(confidence: {pdf_type_result.confidence:.2f})")
            
            # Step 2: Extract blocks based on PDF type
            if pdf_type_result.is_digital:
                blocks = self._extract_blocks_digital(pdf_path)
            else:
                blocks = self._extract_blocks_ocr(pdf_path)
            
            self.logger.info(f"Extracted {len(blocks)} text blocks")
            
            # Step 3: Detect section headers
            section_headers = self.section_detector.detect_section_headers(blocks)
            self.logger.info(f"Detected {len(section_headers)} section headers")
            
            # Step 4: Determine section boundaries
            sections = self.boundary_manager.determine_section_boundaries(section_headers, blocks)
            self.logger.info(f"Created {len(sections)} sections with boundaries")
            
            # Step 5: Classify content types
            content_analyses = {}
            for section in sections:
                content_analysis = self.content_classifier.classify_section_content(section)
                content_analyses[section.section_id] = content_analysis
                
                # Record evidence for content classification
                self._record_content_classification_evidence(section, content_analysis)
            
            # Step 6: Normalize fields in each section
            normalized_fields = {}
            for section in sections:
                section_data = self._extract_section_data(section, content_analyses[section.section_id])
                if section_data:
                    normalized_section_fields = self.field_normalizer.normalize_section_fields(section_data)
                    normalized_fields[section.section_id] = normalized_section_fields
                    
                    # Record evidence for field normalization
                    self._record_field_normalization_evidence(section, normalized_section_fields)
            
            # Step 7: Generate evidence report
            evidence_report = self.evidence_tracker.generate_evidence_report()
            
            # Step 8: Create processing metadata
            processing_metadata = self._create_processing_metadata(
                pdf_type_result, sections, content_analyses, evidence_report
            )
            
            result = ProcessingResult(
                success=True,
                notice_id=notice_id,
                file_name=file_name,
                pdf_type_result=pdf_type_result,
                extracted_sections=sections,
                content_analyses=content_analyses,
                normalized_fields=normalized_fields,
                evidence_report=evidence_report,
                processing_metadata=processing_metadata
            )
            
            self.logger.info(f"Successfully processed {file_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process PDF {pdf_path}: {e}")
            return ProcessingResult(
                success=False,
                notice_id=notice_id,
                file_name=os.path.basename(pdf_path) if pdf_path else "unknown",
                pdf_type_result=PDFTypeResult(False, 0.0, 0.0, False, None, 0, "", "ocr", {}),
                extracted_sections=[],
                content_analyses={},
                normalized_fields={},
                evidence_report={},
                processing_metadata={},
                error_message=str(e)
            )
    
    def _extract_blocks_digital(self, pdf_path: str) -> List[Block]:
        """Extract blocks from digital PDF"""
        blocks = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(min(len(doc), self.max_pages_to_analyze)):
                page = doc[page_num]
                
                # Get text with font information
                text_dict = page.get_text("dict")
                
                # Extract blocks with metadata
                page_blocks = self._extract_blocks_from_dict(text_dict, page_num)
                blocks.extend(page_blocks)
                
                # Record evidence for digital extraction
                for block in page_blocks:
                    evidence = create_evidence_from_extraction(
                        page=page_num,
                        bbox=block.bbox,
                        line_range=(block.block_index, block.block_index),
                        method=ExtractionMethod.PDF_TEXT_EXTRACTION,
                        confidence=0.95,
                        raw_text=block.text
                    )
                    self.evidence_tracker.record_evidence(f"block_{block.block_index}", evidence)
            
            doc.close()
            
        except Exception as e:
            self.logger.error(f"Failed to extract blocks from digital PDF: {e}")
            # Fallback to OCR
            return self._extract_blocks_ocr(pdf_path)
        
        return blocks
    
    def _extract_blocks_ocr(self, pdf_path: str) -> List[Block]:
        """Extract blocks using OCR"""
        blocks = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(min(len(doc), self.max_pages_to_analyze)):
                page = doc[page_num]
                
                # Convert page to image
                mat = fitz.Matrix(self.image_dpi / 72, self.image_dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Run OCR
                ocr_data = pytesseract.image_to_data(
                    img, 
                    config=self.ocr_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Process OCR results into blocks
                page_blocks = self._process_ocr_data(ocr_data, page_num)
                blocks.extend(page_blocks)
                
                # Record evidence for OCR extraction
                for block in page_blocks:
                    confidence = self.confidence_calculator.calculate_ocr_confidence(
                        block.confidence, len(block.text)
                    )
                    
                    evidence = create_evidence_from_extraction(
                        page=page_num,
                        bbox=block.bbox,
                        line_range=(block.block_index, block.block_index),
                        method=ExtractionMethod.OCR_TESSERACT,
                        confidence=confidence,
                        raw_text=block.text
                    )
                    self.evidence_tracker.record_evidence(f"block_{block.block_index}", evidence)
            
            doc.close()
            
        except Exception as e:
            self.logger.error(f"Failed to extract blocks using OCR: {e}")
            raise
        
        return blocks
    
    def _extract_blocks_from_dict(self, text_dict: Dict, page_num: int) -> List[Block]:
        """Extract blocks from PyMuPDF text dictionary"""
        blocks = []
        block_index = 0
        
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            
            # Combine lines in block
            block_text_parts = []
            font_sizes = []
            is_bold_flags = []
            
            for line in block["lines"]:
                line_text_parts = []
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        line_text_parts.append(text)
                        
                        # Collect font metadata
                        if span.get("size"):
                            font_sizes.append(span["size"])
                        if span.get("flags") is not None:
                            # Check for bold (flag & 16)
                            is_bold_flags.append(bool(span["flags"] & 16))
                
                if line_text_parts:
                    block_text_parts.append(" ".join(line_text_parts))
            
            if block_text_parts:
                combined_text = "\n".join(block_text_parts)
                
                # Calculate metadata
                avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else None
                is_bold = any(is_bold_flags) if is_bold_flags else None
                
                # Get bounding box
                bbox = block.get("bbox", [0, 0, 0, 0])
                
                block_obj = Block(
                    page=page_num,
                    bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                    text=combined_text,
                    font_size=avg_font_size,
                    is_bold=is_bold,
                    confidence=1.0,
                    block_index=block_index
                )
                
                blocks.append(block_obj)
                block_index += 1
        
        return blocks
    
    def _process_ocr_data(self, ocr_data: Dict, page_num: int) -> List[Block]:
        """Process OCR data into blocks"""
        blocks = []
        
        # Group words into lines and blocks
        current_line = []
        current_line_top = None
        line_threshold = 10  # pixels
        
        words_data = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            
            if text and conf > 30:  # Filter low confidence words
                words_data.append({
                    'text': text,
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i],
                    'conf': conf
                })
        
        # Group words into lines
        lines = []
        words_data.sort(key=lambda w: (w['top'], w['left']))
        
        for word in words_data:
            if current_line_top is None or abs(word['top'] - current_line_top) <= line_threshold:
                current_line.append(word)
                current_line_top = word['top']
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
                current_line_top = word['top']
        
        if current_line:
            lines.append(current_line)
        
        # Convert lines to blocks
        for i, line in enumerate(lines):
            if not line:
                continue
            
            # Combine text
            line_text = " ".join(word['text'] for word in line)
            
            # Calculate bounding box
            left = min(word['left'] for word in line)
            top = min(word['top'] for word in line)
            right = max(word['left'] + word['width'] for word in line)
            bottom = max(word['top'] + word['height'] for word in line)
            
            # Calculate average confidence
            avg_conf = sum(word['conf'] for word in line) / len(line) / 100.0
            
            block = Block(
                page=page_num,
                bbox=(left, top, right, bottom),
                text=line_text,
                confidence=avg_conf,
                block_index=i
            )
            
            blocks.append(block)
        
        return blocks
    
    def _record_content_classification_evidence(self, section: Section, analysis: ContentAnalysis):
        """Record evidence for content classification"""
        confidence = self.confidence_calculator.calculate_layout_confidence(
            analysis.characteristics.get('alignment_score', 0.5),
            0.7,  # consistency score
            0.6   # position score
        )
        
        evidence = Evidence(
            source_page=section.header.block.page,
            bbox=BoundingBox(
                section.header.block.page,
                section.header.block.bbox[0],
                section.header.block.bbox[1],
                section.header.block.bbox[2],
                section.header.block.bbox[3]
            ),
            line_range=(section.start_block_index, section.end_block_index),
            extraction_method=ExtractionMethod.HEURISTIC_ANALYSIS,
            confidence=confidence,
            raw_text=section.header.block.text,
            validation_notes=[f"Content type: {analysis.content_type}"]
        )
        
        self.evidence_tracker.record_evidence(f"content_type_{section.section_id}", evidence)
    
    def _record_field_normalization_evidence(self, section: Section, 
                                           normalized_fields: Dict[str, NormalizedField]):
        """Record evidence for field normalization"""
        for field_name, normalized_field in normalized_fields.items():
            if normalized_field.validation_status == 'valid':
                confidence = normalized_field.confidence
            else:
                confidence = 0.3
            
            evidence = Evidence(
                source_page=section.header.block.page,
                bbox=BoundingBox(
                    section.header.block.page,
                    section.header.block.bbox[0],
                    section.header.block.bbox[1],
                    section.header.block.bbox[2],
                    section.header.block.bbox[3]
                ),
                line_range=(section.start_block_index, section.end_block_index),
                extraction_method=ExtractionMethod.PATTERN_MATCHING,
                confidence=confidence,
                raw_text=normalized_field.original_value,
                pattern_matched=field_name,
                validation_notes=[normalized_field.validation_status]
            )
            
            self.evidence_tracker.record_evidence(field_name, evidence)
    
    def _extract_section_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract structured data from section content"""
        section_data = {}
        
        # Extract based on section label
        if section.header.normalized_label == 'ASSET_OVERVIEW':
            section_data.update(self._extract_asset_data(section, analysis))
        elif section.header.normalized_label == 'BID_SCHEDULE':
            section_data.update(self._extract_bid_schedule_data(section, analysis))
        elif section.header.normalized_label == 'BID_METHOD':
            section_data.update(self._extract_bid_method_data(section, analysis))
        elif section.header.normalized_label == 'QUALIFICATION':
            section_data.update(self._extract_qualification_data(section, analysis))
        elif section.header.normalized_label == 'PAYMENT':
            section_data.update(self._extract_payment_data(section, analysis))
        elif section.header.normalized_label == 'CONTACT':
            section_data.update(self._extract_contact_data(section, analysis))
        
        return section_data
    
    def _extract_asset_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract asset-related data"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        # Patent number extraction
        import re
        patent_match = re.search(r'특허\s*(?:제|번호)?\s*(\d+(?:-\d+)*)\s*호?', combined_text)
        if patent_match:
            data['patent_number'] = patent_match.group(1)
        
        # Registration number
        reg_match = re.search(r'등록\s*(?:번호)?\s*(\d+(?:-\d+)*)', combined_text)
        if reg_match:
            data['registration_number'] = reg_match.group(1)
        
        # Asset description
        if len(combined_text) > 50:
            data['asset_description'] = combined_text[:500]
        
        return data
    
    def _extract_bid_schedule_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract bid schedule data"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        import re
        # Date patterns
        date_matches = re.findall(r'(\d{4})[년.-]\s*(\d{1,2})[월.-]\s*(\d{1,2})[일]?', combined_text)
        if date_matches:
            if len(date_matches) >= 1:
                data['bid_start'] = f"{date_matches[0][0]}-{date_matches[0][1]:0>2}-{date_matches[0][2]:0>2}"
            if len(date_matches) >= 2:
                data['bid_end'] = f"{date_matches[1][0]}-{date_matches[1][1]:0>2}-{date_matches[1][2]:0>2}"
            if len(date_matches) >= 3:
                data['opening_date'] = f"{date_matches[2][0]}-{date_matches[2][1]:0>2}-{date_matches[2][2]:0>2}"
        
        return data
    
    def _extract_bid_method_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract bid method data"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        if '서면' in combined_text:
            data['bid_method'] = '서면입찰'
        elif '전자' in combined_text:
            data['bid_method'] = '전자입찰'
        else:
            data['bid_method'] = combined_text[:100]
        
        return data
    
    def _extract_qualification_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract qualification requirements"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        data['qualification_requirements'] = combined_text[:1000]
        
        return data
    
    def _extract_payment_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract payment-related data"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        import re
        # Money amounts
        money_matches = re.findall(r'(\d{1,3}(?:[,]\d{3})*)\s*만?\s*원', combined_text)
        if money_matches:
            if '최저' in combined_text or '시작' in combined_text:
                data['minimum_bid'] = money_matches[0]
            if '보증금' in combined_text:
                data['bid_deposit'] = money_matches[0] if len(money_matches) == 1 else money_matches[1]
        
        return data
    
    def _extract_contact_data(self, section: Section, analysis: ContentAnalysis) -> Dict[str, str]:
        """Extract contact information"""
        data = {}
        combined_text = " ".join(block.text for block in section.content_blocks)
        
        import re
        # Phone numbers
        phone_match = re.search(r'(\d{2,3})-(\d{3,4})-(\d{4})', combined_text)
        if phone_match:
            data['contact_phone'] = f"{phone_match.group(1)}-{phone_match.group(2)}-{phone_match.group(3)}"
        
        # Extract organization name
        org_match = re.search(r'(법무법인\s*[가-힣\s]+|변호사\s*[가-힣\s]+)', combined_text)
        if org_match:
            data['contact_organization'] = org_match.group(1)
        
        return data
    
    def _create_processing_metadata(self, pdf_type_result: PDFTypeResult, 
                                  sections: List[Section], 
                                  content_analyses: Dict[str, ContentAnalysis],
                                  evidence_report: Dict[str, Any]) -> Dict[str, Any]:
        """Create processing metadata"""
        return {
            'pdf_processing': {
                'type': 'digital' if pdf_type_result.is_digital else 'scanned',
                'type_confidence': pdf_type_result.confidence,
                'processing_method': pdf_type_result.processing_method,
                'total_pages': pdf_type_result.total_pages
            },
            'section_processing': {
                'total_sections': len(sections),
                'section_types': list(set(s.header.section_type for s in sections)),
                'content_types': list(set(a.content_type for a in content_analyses.values())),
                'cross_page_sections': len([s for s in sections if s.cross_page_continuation]),
                'merged_sections': len([s for s in sections if s.merge_history])
            },
            'quality_metrics': {
                'overall_confidence': evidence_report.get('summary', {}).get('overall_confidence', 0.0),
                'evidence_density': evidence_report.get('evidence_density', 0.0),
                'unknown_sections': len([s for s in sections if s.header.normalized_label == 'UNKNOWN']),
                'low_confidence_sections': len([s for s in sections if s.confidence < 0.5])
            },
            'extraction_methods': evidence_report.get('method_usage', {}),
            'confidence_distribution': evidence_report.get('confidence_distribution', {})
        }


def test_rule_based_processor():
    """Test the rule-based processor"""
    processor = RuleBasedPDFProcessor()
    
    # Test with available PDF files
    downloads_dir = Path("downloads")
    if downloads_dir.exists():
        for notice_dir in downloads_dir.iterdir():
            if notice_dir.is_dir() and notice_dir.name.startswith('notice_'):
                for pdf_file in notice_dir.glob('*.pdf'):
                    notice_id = notice_dir.name.split('_')[1]
                    
                    print(f"\\nTesting rule-based processing: {pdf_file.name}")
                    
                    result = processor.process_pdf(str(pdf_file), notice_id)
                    
                    if result.success:
                        print(f"✅ Success!")
                        print(f"   PDF Type: {'Digital' if result.pdf_type_result.is_digital else 'Scanned'}")
                        print(f"   Sections: {len(result.extracted_sections)}")
                        print(f"   Overall Confidence: {result.evidence_report.get('summary', {}).get('overall_confidence', 0):.2f}")
                        
                        # Show section summary
                        for section in result.extracted_sections[:3]:
                            print(f"   - {section.header.normalized_label}: {section.header.block.text[:50]}...")
                    else:
                        print(f"❌ Failed: {result.error_message}")
                    
                    break  # Test only first PDF
                break  # Test only first directory


if __name__ == "__main__":
    test_rule_based_processor()