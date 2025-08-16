"""
PDF Type Detection System
Determines if PDF is digital or scanned for optimal processing strategy
"""
import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from utils.logger import setup_logger


@dataclass
class PDFTypeResult:
    """Result of PDF type detection"""
    is_digital: bool
    confidence: float
    text_extraction_success_rate: float
    has_font_metadata: bool
    avg_char_confidence: Optional[float]
    total_pages: int
    sample_text: str
    processing_method: str  # "digital" or "ocr"
    evidence: Dict[str, Any]


class PDFTypeDetector:
    """Detects whether PDF is digital or scanned"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Thresholds for digital PDF detection
        self.DIGITAL_TEXT_THRESHOLD = 0.7  # 70% of pages must have extractable text
        self.MIN_CHARS_PER_PAGE = 50       # Minimum characters to consider page as text-rich
        self.FONT_CONFIDENCE_BONUS = 0.2   # Bonus for having font metadata
        
        # OCR configuration
        self.tesseract_config = '--oem 1 --psm 4 -l kor+eng'
        
    def detect_pdf_type(self, pdf_path: str) -> PDFTypeResult:
        """
        Detect PDF type and determine optimal processing strategy
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            PDFTypeResult with detection results
        """
        try:
            self.logger.info(f"Detecting PDF type for: {pdf_path}")
            
            # Open PDF document
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # Analyze first few pages for type detection
            sample_pages = min(3, total_pages)
            
            text_extraction_results = []
            font_metadata_found = False
            sample_texts = []
            
            for page_num in range(sample_pages):
                page = doc[page_num]
                
                # Try text extraction
                text = page.get_text()
                char_count = len(text.strip())
                
                # Check for font metadata
                if not font_metadata_found:
                    text_dict = page.get_text("dict")
                    font_metadata_found = self._has_font_metadata(text_dict)
                
                # Record extraction success
                extraction_success = char_count >= self.MIN_CHARS_PER_PAGE
                text_extraction_results.append({
                    'page': page_num,
                    'char_count': char_count,
                    'success': extraction_success,
                    'text_sample': text[:200] if text else ""
                })
                
                if extraction_success:
                    sample_texts.append(text[:500])
            
            doc.close()
            
            # Calculate success rate
            success_count = sum(1 for result in text_extraction_results if result['success'])
            text_success_rate = success_count / sample_pages if sample_pages > 0 else 0.0
            
            # Determine if digital
            base_confidence = text_success_rate
            if font_metadata_found:
                base_confidence += self.FONT_CONFIDENCE_BONUS
            
            is_digital = base_confidence >= self.DIGITAL_TEXT_THRESHOLD
            
            # Get OCR confidence for comparison if needed
            ocr_confidence = None
            if not is_digital and sample_pages > 0:
                ocr_confidence = self._test_ocr_quality(pdf_path, 0)
            
            # Determine processing method
            processing_method = "digital" if is_digital else "ocr"
            
            # Prepare evidence
            evidence = {
                'extraction_results': text_extraction_results,
                'font_metadata_found': font_metadata_found,
                'sample_pages_analyzed': sample_pages,
                'base_confidence': base_confidence,
                'ocr_test_confidence': ocr_confidence
            }
            
            result = PDFTypeResult(
                is_digital=is_digital,
                confidence=min(1.0, base_confidence),
                text_extraction_success_rate=text_success_rate,
                has_font_metadata=font_metadata_found,
                avg_char_confidence=ocr_confidence,
                total_pages=total_pages,
                sample_text=" ".join(sample_texts)[:1000],
                processing_method=processing_method,
                evidence=evidence
            )
            
            self.logger.info(f"PDF type detected: {'Digital' if is_digital else 'Scanned'} "
                           f"(confidence: {result.confidence:.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect PDF type: {e}")
            # Return fallback result suggesting OCR
            return PDFTypeResult(
                is_digital=False,
                confidence=0.0,
                text_extraction_success_rate=0.0,
                has_font_metadata=False,
                avg_char_confidence=None,
                total_pages=0,
                sample_text="",
                processing_method="ocr",
                evidence={'error': str(e)}
            )
    
    def _has_font_metadata(self, text_dict: Dict) -> bool:
        """Check if page has font metadata (indicates digital PDF)"""
        try:
            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line.get("spans", []):
                            # Check for font information
                            if span.get("font") and span.get("size"):
                                return True
            return False
        except:
            return False
    
    def _test_ocr_quality(self, pdf_path: str, page_num: int) -> Optional[float]:
        """Test OCR quality on a sample page"""
        try:
            # Convert page to image
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            
            # Render at higher resolution for better OCR
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            doc.close()
            
            # Run OCR with confidence data
            try:
                ocr_data = pytesseract.image_to_data(
                    img, 
                    config=self.tesseract_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Calculate average confidence for words with confidence > 0
                confidences = [
                    int(conf) for conf in ocr_data.get('conf', []) 
                    if int(conf) > 0
                ]
                
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences) / 100.0
                    return avg_confidence
                
            except Exception as ocr_error:
                self.logger.warning(f"OCR test failed: {ocr_error}")
                return None
                
        except Exception as e:
            self.logger.warning(f"OCR quality test failed: {e}")
            return None
        
        return None
    
    def get_processing_recommendation(self, result: PDFTypeResult) -> Dict[str, Any]:
        """Get processing recommendations based on detection result"""
        if result.is_digital:
            return {
                'method': 'digital',
                'tools': ['PyMuPDF', 'pdfplumber'],
                'extract_coordinates': True,
                'extract_fonts': True,
                'confidence': result.confidence
            }
        else:
            return {
                'method': 'ocr',
                'tools': ['Tesseract', 'OpenCV'],
                'preprocess_image': True,
                'dpi': 300,
                'config': self.tesseract_config,
                'confidence': result.avg_char_confidence or 0.5
            }


def test_pdf_type_detection():
    """Test PDF type detection functionality"""
    detector = PDFTypeDetector()
    
    # Test with available PDF files
    downloads_dir = "downloads"
    if os.path.exists(downloads_dir):
        for notice_dir in os.listdir(downloads_dir):
            notice_path = os.path.join(downloads_dir, notice_dir)
            if os.path.isdir(notice_path):
                for file in os.listdir(notice_path):
                    if file.endswith('.pdf'):
                        pdf_path = os.path.join(notice_path, file)
                        print(f"\nTesting: {file}")
                        
                        result = detector.detect_pdf_type(pdf_path)
                        print(f"Type: {'Digital' if result.is_digital else 'Scanned'}")
                        print(f"Confidence: {result.confidence:.2f}")
                        print(f"Text Success Rate: {result.text_extraction_success_rate:.2f}")
                        print(f"Has Font Metadata: {result.has_font_metadata}")
                        print(f"Processing Method: {result.processing_method}")
                        
                        # Get recommendations
                        recommendation = detector.get_processing_recommendation(result)
                        print(f"Recommended Method: {recommendation['method']}")
                        
                        break  # Test only first PDF in each directory
                break  # Test only first directory


if __name__ == "__main__":
    test_pdf_type_detection()