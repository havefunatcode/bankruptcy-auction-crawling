"""
Evidence and Confidence System
Tracks evidence for all extracted data and calculates confidence scores
"""
import json
from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
from utils.logger import setup_logger


class ExtractionMethod(Enum):
    """Methods used for data extraction"""
    PDF_TEXT_EXTRACTION = "pdf_text_extraction"
    OCR_TESSERACT = "ocr_tesseract"
    PATTERN_MATCHING = "pattern_matching"
    HEURISTIC_ANALYSIS = "heuristic_analysis"
    LAYOUT_ANALYSIS = "layout_analysis"
    FONT_ANALYSIS = "font_analysis"
    CONTEXT_INFERENCE = "context_inference"


@dataclass
class BoundingBox:
    """Bounding box coordinates"""
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    
    def to_dict(self) -> Dict[str, Union[int, float]]:
        return asdict(self)
    
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass
class Evidence:
    """Evidence for extracted data"""
    source_page: int
    bbox: BoundingBox
    line_range: Tuple[int, int]  # start_line, end_line
    extraction_method: ExtractionMethod
    confidence: float
    raw_text: str
    pattern_matched: Optional[str] = None
    validation_notes: List[str] = None
    cross_references: List[str] = None
    
    def __post_init__(self):
        if self.validation_notes is None:
            self.validation_notes = []
        if self.cross_references is None:
            self.cross_references = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_page': self.source_page,
            'bbox': self.bbox.to_dict(),
            'line_range': list(self.line_range),
            'extraction_method': self.extraction_method.value,
            'confidence': self.confidence,
            'raw_text': self.raw_text,
            'pattern_matched': self.pattern_matched,
            'validation_notes': self.validation_notes,
            'cross_references': self.cross_references
        }


@dataclass
class ExtractedValue:
    """Extracted value with evidence chain"""
    field_name: str
    raw_value: str
    normalized_value: Any
    data_type: str
    evidence_chain: List[Evidence]
    overall_confidence: float
    validation_status: str
    notes: List[str] = None
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []
    
    def add_evidence(self, evidence: Evidence):
        """Add evidence to the chain"""
        self.evidence_chain.append(evidence)
        self._recalculate_confidence()
    
    def _recalculate_confidence(self):
        """Recalculate overall confidence based on evidence chain"""
        if not self.evidence_chain:
            self.overall_confidence = 0.0
            return
        
        # Weight evidences by their confidence and method reliability
        weighted_confidences = []
        method_weights = {
            ExtractionMethod.PDF_TEXT_EXTRACTION: 1.0,
            ExtractionMethod.PATTERN_MATCHING: 0.9,
            ExtractionMethod.LAYOUT_ANALYSIS: 0.8,
            ExtractionMethod.FONT_ANALYSIS: 0.7,
            ExtractionMethod.OCR_TESSERACT: 0.7,
            ExtractionMethod.HEURISTIC_ANALYSIS: 0.6,
            ExtractionMethod.CONTEXT_INFERENCE: 0.5
        }
        
        for evidence in self.evidence_chain:
            method_weight = method_weights.get(evidence.extraction_method, 0.5)
            weighted_confidence = evidence.confidence * method_weight
            weighted_confidences.append(weighted_confidence)
        
        # Use maximum confidence (best evidence wins)
        self.overall_confidence = max(weighted_confidences)
        
        # Bonus for multiple supporting evidences
        if len(self.evidence_chain) > 1:
            # Small bonus for corroboration, up to 0.1
            bonus = min(0.1, (len(self.evidence_chain) - 1) * 0.03)
            self.overall_confidence = min(1.0, self.overall_confidence + bonus)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_name': self.field_name,
            'raw_value': self.raw_value,
            'normalized_value': self.normalized_value,
            'data_type': self.data_type,
            'evidence_chain': [e.to_dict() for e in self.evidence_chain],
            'overall_confidence': self.overall_confidence,
            'validation_status': self.validation_status,
            'notes': self.notes
        }


class EvidenceTracker:
    """Tracks evidence for all extractions"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.evidence_store: Dict[str, List[Evidence]] = {}
        self.confidence_history: List[float] = []
        
        # Confidence thresholds
        self.HIGH_CONFIDENCE_THRESHOLD = 0.8
        self.MEDIUM_CONFIDENCE_THRESHOLD = 0.5
        self.LOW_CONFIDENCE_THRESHOLD = 0.3
    
    def record_evidence(self, field_name: str, evidence: Evidence):
        """Record evidence for a field"""
        if field_name not in self.evidence_store:
            self.evidence_store[field_name] = []
        
        self.evidence_store[field_name].append(evidence)
        self.confidence_history.append(evidence.confidence)
        
        self.logger.debug(f"Recorded evidence for {field_name}: {evidence.extraction_method.value} "
                         f"(confidence: {evidence.confidence:.2f})")
    
    def create_extracted_value(self, field_name: str, raw_value: str, 
                             normalized_value: Any, data_type: str) -> ExtractedValue:
        """Create ExtractedValue with associated evidence"""
        evidence_chain = self.evidence_store.get(field_name, [])
        
        extracted_value = ExtractedValue(
            field_name=field_name,
            raw_value=raw_value,
            normalized_value=normalized_value,
            data_type=data_type,
            evidence_chain=evidence_chain,
            overall_confidence=0.0,
            validation_status='pending'
        )
        
        # Calculate confidence
        extracted_value._recalculate_confidence()
        
        # Determine validation status
        if extracted_value.overall_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            extracted_value.validation_status = 'high_confidence'
        elif extracted_value.overall_confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            extracted_value.validation_status = 'medium_confidence'
        elif extracted_value.overall_confidence >= self.LOW_CONFIDENCE_THRESHOLD:
            extracted_value.validation_status = 'low_confidence'
        else:
            extracted_value.validation_status = 'very_low_confidence'
        
        return extracted_value
    
    def add_validation_note(self, field_name: str, note: str):
        """Add validation note to all evidence for a field"""
        if field_name in self.evidence_store:
            for evidence in self.evidence_store[field_name]:
                evidence.validation_notes.append(note)
    
    def add_cross_reference(self, field_name: str, reference: str):
        """Add cross reference to evidence"""
        if field_name in self.evidence_store:
            for evidence in self.evidence_store[field_name]:
                evidence.cross_references.append(reference)
    
    def get_field_confidence(self, field_name: str) -> float:
        """Get overall confidence for a field"""
        if field_name not in self.evidence_store:
            return 0.0
        
        confidences = [e.confidence for e in self.evidence_store[field_name]]
        return max(confidences) if confidences else 0.0
    
    def get_overall_confidence(self) -> float:
        """Get overall confidence across all fields"""
        if not self.confidence_history:
            return 0.0
        
        return statistics.mean(self.confidence_history)
    
    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence levels"""
        distribution = {'high': 0, 'medium': 0, 'low': 0, 'very_low': 0}
        
        for confidence in self.confidence_history:
            if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                distribution['high'] += 1
            elif confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
                distribution['medium'] += 1
            elif confidence >= self.LOW_CONFIDENCE_THRESHOLD:
                distribution['low'] += 1
            else:
                distribution['very_low'] += 1
        
        return distribution
    
    def identify_low_confidence_fields(self) -> List[str]:
        """Identify fields with low confidence that need review"""
        low_confidence_fields = []
        
        for field_name, evidences in self.evidence_store.items():
            if evidences:
                max_confidence = max(e.confidence for e in evidences)
                if max_confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
                    low_confidence_fields.append(field_name)
        
        return low_confidence_fields
    
    def generate_evidence_report(self) -> Dict[str, Any]:
        """Generate comprehensive evidence report"""
        total_fields = len(self.evidence_store)
        total_evidences = sum(len(evidences) for evidences in self.evidence_store.values())
        
        confidence_dist = self.get_confidence_distribution()
        low_confidence_fields = self.identify_low_confidence_fields()
        
        # Method usage statistics
        method_usage = {}
        for evidences in self.evidence_store.values():
            for evidence in evidences:
                method = evidence.extraction_method.value
                method_usage[method] = method_usage.get(method, 0) + 1
        
        # Page coverage analysis
        page_coverage = set()
        for evidences in self.evidence_store.values():
            for evidence in evidences:
                page_coverage.add(evidence.source_page)
        
        return {
            'summary': {
                'total_fields': total_fields,
                'total_evidences': total_evidences,
                'overall_confidence': self.get_overall_confidence(),
                'pages_covered': len(page_coverage)
            },
            'confidence_distribution': confidence_dist,
            'low_confidence_fields': low_confidence_fields,
            'method_usage': method_usage,
            'evidence_density': total_evidences / total_fields if total_fields > 0 else 0
        }
    
    def export_evidence_data(self) -> Dict[str, Any]:
        """Export all evidence data for storage"""
        return {
            'evidence_store': {
                field: [e.to_dict() for e in evidences]
                for field, evidences in self.evidence_store.items()
            },
            'confidence_history': self.confidence_history,
            'thresholds': {
                'high': self.HIGH_CONFIDENCE_THRESHOLD,
                'medium': self.MEDIUM_CONFIDENCE_THRESHOLD,
                'low': self.LOW_CONFIDENCE_THRESHOLD
            }
        }


class ConfidenceCalculator:
    """Calculates confidence scores based on various factors"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
    
    def calculate_pattern_confidence(self, pattern: str, match_quality: float, 
                                   context_support: float = 0.0) -> float:
        """Calculate confidence for pattern-based extraction"""
        # Base confidence from match quality
        base_confidence = match_quality
        
        # Pattern complexity bonus
        pattern_complexity = self._assess_pattern_complexity(pattern)
        complexity_bonus = pattern_complexity * 0.1
        
        # Context support bonus
        context_bonus = context_support * 0.2
        
        total_confidence = min(1.0, base_confidence + complexity_bonus + context_bonus)
        
        self.logger.debug(f"Pattern confidence: base={base_confidence:.2f}, "
                         f"complexity={complexity_bonus:.2f}, context={context_bonus:.2f}, "
                         f"total={total_confidence:.2f}")
        
        return total_confidence
    
    def calculate_ocr_confidence(self, avg_char_confidence: float, 
                               text_length: int, language_match: float = 0.8) -> float:
        """Calculate confidence for OCR extraction"""
        # Base confidence from OCR engine
        base_confidence = avg_char_confidence
        
        # Length bonus (longer text is more reliable if confidence is high)
        if base_confidence > 0.7 and text_length > 10:
            length_bonus = min(0.1, text_length / 200)
        else:
            length_bonus = 0.0
        
        # Language match bonus
        language_bonus = language_match * 0.1
        
        total_confidence = min(1.0, base_confidence + length_bonus + language_bonus)
        
        return total_confidence
    
    def calculate_layout_confidence(self, alignment_score: float, 
                                  consistency_score: float, 
                                  position_score: float) -> float:
        """Calculate confidence for layout-based extraction"""
        # Weighted combination of layout factors
        weights = {'alignment': 0.4, 'consistency': 0.3, 'position': 0.3}
        
        weighted_score = (
            alignment_score * weights['alignment'] +
            consistency_score * weights['consistency'] +
            position_score * weights['position']
        )
        
        return min(1.0, weighted_score)
    
    def calculate_cross_validation_confidence(self, primary_confidence: float,
                                            supporting_evidences: List[float]) -> float:
        """Calculate confidence when multiple sources support the same value"""
        if not supporting_evidences:
            return primary_confidence
        
        # Average supporting confidence
        avg_support = statistics.mean(supporting_evidences)
        
        # Boost based on agreement
        if avg_support > 0.7:
            boost = 0.1 * len(supporting_evidences)
            return min(1.0, primary_confidence + boost)
        elif avg_support > 0.5:
            boost = 0.05 * len(supporting_evidences)
            return min(1.0, primary_confidence + boost)
        else:
            # Conflicting evidence reduces confidence
            reduction = 0.1 * len(supporting_evidences)
            return max(0.0, primary_confidence - reduction)
    
    def _assess_pattern_complexity(self, pattern: str) -> float:
        """Assess the complexity/specificity of a regex pattern"""
        complexity_indicators = [
            (r'\d{4}', 0.3),  # Year pattern
            (r'\d{2,3}-\d{3,4}-\d{4}', 0.5),  # Phone pattern
            (r'[가-힣]+', 0.2),  # Korean text
            (r'\w+@\w+\.\w+', 0.4),  # Email pattern
            (r'\(\d+\)', 0.3),  # Parentheses with number
        ]
        
        complexity_score = 0.0
        for indicator, score in complexity_indicators:
            if indicator in pattern:
                complexity_score += score
        
        return min(1.0, complexity_score)


def create_evidence_from_extraction(page: int, bbox: Tuple[float, float, float, float],
                                   line_range: Tuple[int, int], method: ExtractionMethod,
                                   confidence: float, raw_text: str,
                                   pattern: Optional[str] = None) -> Evidence:
    """Convenience function to create Evidence object"""
    bbox_obj = BoundingBox(page, bbox[0], bbox[1], bbox[2], bbox[3])
    
    return Evidence(
        source_page=page,
        bbox=bbox_obj,
        line_range=line_range,
        extraction_method=method,
        confidence=confidence,
        raw_text=raw_text,
        pattern_matched=pattern
    )


# Validation functions

def validate_evidence_completeness(extracted_values: List[ExtractedValue]) -> Dict[str, Any]:
    """Validate that all extracted values have proper evidence"""
    validation_results = {
        'total_values': len(extracted_values),
        'values_with_evidence': 0,
        'values_without_evidence': 0,
        'average_evidence_per_value': 0.0,
        'fields_without_evidence': []
    }
    
    evidence_counts = []
    
    for value in extracted_values:
        if value.evidence_chain:
            validation_results['values_with_evidence'] += 1
            evidence_counts.append(len(value.evidence_chain))
        else:
            validation_results['values_without_evidence'] += 1
            validation_results['fields_without_evidence'].append(value.field_name)
    
    if evidence_counts:
        validation_results['average_evidence_per_value'] = statistics.mean(evidence_counts)
    
    return validation_results


def check_evidence_coverage(extracted_values: List[ExtractedValue], 
                          total_pages: int) -> Dict[str, Any]:
    """Check evidence coverage across document pages"""
    pages_with_evidence = set()
    total_evidences = 0
    
    for value in extracted_values:
        for evidence in value.evidence_chain:
            pages_with_evidence.add(evidence.source_page)
            total_evidences += 1
    
    coverage_ratio = len(pages_with_evidence) / total_pages if total_pages > 0 else 0.0
    
    return {
        'total_pages': total_pages,
        'pages_with_evidence': len(pages_with_evidence),
        'coverage_ratio': coverage_ratio,
        'total_evidences': total_evidences,
        'evidence_density': total_evidences / total_pages if total_pages > 0 else 0.0
    }