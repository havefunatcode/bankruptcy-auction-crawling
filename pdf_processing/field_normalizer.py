"""
Field Normalization and Validation System
Normalizes and validates extracted fields with evidence tracking
"""
import re
import datetime
from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from utils.logger import setup_logger


@dataclass
class NormalizedField:
    """Normalized field with evidence and validation"""
    field_name: str
    original_value: str
    normalized_value: Any
    data_type: str
    confidence: float
    validation_status: str  # 'valid', 'invalid', 'warning'
    evidence: Dict[str, Any]
    validation_errors: List[str]


@dataclass
class ValidationRule:
    """Validation rule for logical checks"""
    rule_name: str
    fields: List[str]
    rule_function: callable
    error_message: str
    severity: str  # 'error', 'warning'


class FieldNormalizer:
    """Normalizes and validates extracted fields"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        
        # Date patterns (Korean documents)
        self.date_patterns = [
            # Full date patterns
            (r'(\d{4})[년.-]\s*(\d{1,2})[월.-]\s*(\d{1,2})[일]?', 'korean_full'),
            (r'(\d{4})-(\d{2})-(\d{2})', 'iso_date'),
            (r'(\d{4})\.(\d{2})\.(\d{2})', 'dot_date'),
            (r'(\d{4})/(\d{2})/(\d{2})', 'slash_date'),
            
            # With time
            (r'(\d{4})[년.-]\s*(\d{1,2})[월.-]\s*(\d{1,2})[일]?\s*(\d{1,2})[시:]\s*(\d{1,2})[분]?', 'korean_datetime'),
            (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})', 'iso_datetime'),
            
            # Partial dates
            (r'(\d{1,2})[월.-]\s*(\d{1,2})[일]?', 'month_day'),
            (r'(\d{1,2})[일]?\s*(\d{1,2})[시:]', 'day_hour'),
        ]
        
        # Money patterns
        self.money_patterns = [
            (r'(\d{1,3}(?:[,]\d{3})*)\s*억\s*(\d{1,3}(?:[,]\d{3})*)?만?\s*원?', 'korean_large'),
            (r'(\d{1,3}(?:[,]\d{3})*)\s*만\s*원?', 'korean_man'),
            (r'(\d{1,3}(?:[,]\d{3})*)\s*원', 'korean_won'),
            (r'(\d{1,3}(?:[,]\d{3})*)', 'number_only'),
        ]
        
        # Phone patterns
        self.phone_patterns = [
            (r'(\d{2,3})-(\d{3,4})-(\d{4})', 'standard'),
            (r'(\d{3})(\d{4})(\d{4})', 'mobile_no_dash'),
            (r'(\d{2})(\d{3,4})(\d{4})', 'landline_no_dash'),
        ]
        
        # Registration number patterns
        self.registration_patterns = [
            (r'특허\s*(?:제|번호)?\s*(\d+(?:-\d+)*)\s*호?', 'patent'),
            (r'등록\s*(?:번호)?\s*(\d+(?:-\d+)*)', 'registration'),
            (r'출원\s*(?:번호)?\s*(\d+(?:-\d+)*)', 'application'),
            (r'실용신안\s*(?:제|번호)?\s*(\d+(?:-\d+)*)\s*호?', 'utility_model'),
        ]
        
        # Validation rules
        self.validation_rules = [
            ValidationRule(
                'bid_schedule_logic',
                ['bid_start', 'bid_end', 'opening_date'],
                self._validate_bid_schedule,
                'Bidding schedule is logically inconsistent',
                'error'
            ),
            ValidationRule(
                'deposit_calculation',
                ['minimum_bid', 'bid_deposit', 'deposit_rate'],
                self._validate_deposit_calculation,
                'Bid deposit calculation is incorrect',
                'warning'
            ),
            ValidationRule(
                'date_format_consistency',
                ['bid_start', 'bid_end', 'opening_date', 'contract_date'],
                self._validate_date_consistency,
                'Date formats are inconsistent',
                'warning'
            ),
        ]
    
    def normalize_section_fields(self, section_data: Dict[str, Any]) -> Dict[str, NormalizedField]:
        """
        Normalize all fields in a section
        
        Args:
            section_data: Raw section data dictionary
            
        Returns:
            Dictionary of normalized fields
        """
        normalized_fields = {}
        
        for field_name, raw_value in section_data.items():
            if raw_value is None or raw_value == '':
                continue
                
            # Determine field type and normalize
            normalized_field = self._normalize_field(field_name, raw_value)
            normalized_fields[field_name] = normalized_field
        
        # Run cross-field validations
        self._run_validation_rules(normalized_fields)
        
        return normalized_fields
    
    def _normalize_field(self, field_name: str, raw_value: str) -> NormalizedField:
        """Normalize a single field"""
        raw_value_str = str(raw_value).strip()
        
        # Determine field type based on name and content
        field_type = self._determine_field_type(field_name, raw_value_str)
        
        # Apply appropriate normalization
        if field_type == 'date':
            return self._normalize_date_field(field_name, raw_value_str)
        elif field_type == 'money':
            return self._normalize_money_field(field_name, raw_value_str)
        elif field_type == 'phone':
            return self._normalize_phone_field(field_name, raw_value_str)
        elif field_type == 'registration':
            return self._normalize_registration_field(field_name, raw_value_str)
        elif field_type == 'text':
            return self._normalize_text_field(field_name, raw_value_str)
        else:
            return self._normalize_generic_field(field_name, raw_value_str)
    
    def _determine_field_type(self, field_name: str, value: str) -> str:
        """Determine the type of field based on name and content"""
        field_name_lower = field_name.lower()
        
        # Date fields
        if any(keyword in field_name_lower for keyword in 
               ['date', 'time', '일시', '기간', '마감', '개찰', '계약']):
            return 'date'
        
        # Money fields
        if any(keyword in field_name_lower for keyword in 
               ['price', 'amount', 'cost', '가격', '금액', '대금', '보증금', '수수료']):
            return 'money'
        
        # Phone fields
        if any(keyword in field_name_lower for keyword in 
               ['phone', 'tel', '전화', '연락처', 'fax']):
            return 'phone'
        
        # Registration numbers
        if any(keyword in field_name_lower for keyword in 
               ['patent', 'registration', '특허', '등록', '출원', '번호']):
            return 'registration'
        
        # Content-based detection
        if re.search(r'\d{4}[년.-]\d{1,2}[월.-]\d{1,2}', value):
            return 'date'
        elif re.search(r'\d+[,.]?\d*\s*(원|만원|억원)', value):
            return 'money'
        elif re.search(r'\d{2,3}-\d{3,4}-\d{4}', value):
            return 'phone'
        elif re.search(r'(특허|등록|출원).*\d+', value):
            return 'registration'
        else:
            return 'text'
    
    def _normalize_date_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize date field"""
        for pattern, pattern_type in self.date_patterns:
            match = re.search(pattern, value)
            if match:
                try:
                    normalized_date, confidence = self._parse_date_match(match, pattern_type)
                    
                    return NormalizedField(
                        field_name=field_name,
                        original_value=value,
                        normalized_value=normalized_date,
                        data_type='datetime',
                        confidence=confidence,
                        validation_status='valid',
                        evidence={
                            'pattern_type': pattern_type,
                            'pattern': pattern,
                            'match_groups': match.groups()
                        },
                        validation_errors=[]
                    )
                except ValueError as e:
                    return NormalizedField(
                        field_name=field_name,
                        original_value=value,
                        normalized_value=None,
                        data_type='datetime',
                        confidence=0.0,
                        validation_status='invalid',
                        evidence={'pattern_type': pattern_type, 'error': str(e)},
                        validation_errors=[f"Date parsing error: {e}"]
                    )
        
        # No pattern matched
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=value,
            data_type='text',
            confidence=0.3,
            validation_status='warning',
            evidence={'no_date_pattern_matched': True},
            validation_errors=["No date pattern matched"]
        )
    
    def _parse_date_match(self, match, pattern_type: str) -> Tuple[datetime.datetime, float]:
        """Parse date match based on pattern type"""
        groups = match.groups()
        
        if pattern_type == 'korean_full':
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            return datetime.datetime(year, month, day), 0.9
        
        elif pattern_type in ['iso_date', 'dot_date', 'slash_date']:
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            return datetime.datetime(year, month, day), 0.95
        
        elif pattern_type == 'korean_datetime':
            year, month, day, hour, minute = map(int, groups)
            return datetime.datetime(year, month, day, hour, minute), 0.9
        
        elif pattern_type == 'iso_datetime':
            year, month, day, hour, minute = map(int, groups)
            return datetime.datetime(year, month, day, hour, minute), 0.95
        
        elif pattern_type == 'month_day':
            # Assume current year
            current_year = datetime.datetime.now().year
            month, day = int(groups[0]), int(groups[1])
            return datetime.datetime(current_year, month, day), 0.6
        
        elif pattern_type == 'day_hour':
            # Very uncertain without full date context
            day, hour = int(groups[0]), int(groups[1])
            current_date = datetime.datetime.now()
            return current_date.replace(day=day, hour=hour, minute=0, second=0), 0.3
        
        else:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
    
    def _normalize_money_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize money field to integer won amount"""
        for pattern, pattern_type in self.money_patterns:
            match = re.search(pattern, value)
            if match:
                try:
                    amount = self._parse_money_match(match, pattern_type)
                    
                    return NormalizedField(
                        field_name=field_name,
                        original_value=value,
                        normalized_value=int(amount),
                        data_type='money',
                        confidence=0.9,
                        validation_status='valid',
                        evidence={
                            'pattern_type': pattern_type,
                            'pattern': pattern,
                            'match_groups': match.groups()
                        },
                        validation_errors=[]
                    )
                except (ValueError, InvalidOperation) as e:
                    return NormalizedField(
                        field_name=field_name,
                        original_value=value,
                        normalized_value=None,
                        data_type='money',
                        confidence=0.0,
                        validation_status='invalid',
                        evidence={'error': str(e)},
                        validation_errors=[f"Money parsing error: {e}"]
                    )
        
        # Try to extract any number
        number_match = re.search(r'(\d{1,3}(?:[,]\d{3})*|\d+)', value)
        if number_match:
            try:
                amount = int(number_match.group(1).replace(',', ''))
                return NormalizedField(
                    field_name=field_name,
                    original_value=value,
                    normalized_value=amount,
                    data_type='money',
                    confidence=0.5,
                    validation_status='warning',
                    evidence={'fallback_number_extraction': True},
                    validation_errors=["Used fallback number extraction"]
                )
            except ValueError:
                pass
        
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=None,
            data_type='money',
            confidence=0.0,
            validation_status='invalid',
            evidence={'no_money_pattern_matched': True},
            validation_errors=["No money pattern matched"]
        )
    
    def _parse_money_match(self, match, pattern_type: str) -> int:
        """Parse money match to won amount"""
        groups = match.groups()
        
        if pattern_type == 'korean_large':
            # X억 Y만원 format
            eok_part = int(groups[0].replace(',', '')) if groups[0] else 0
            man_part = int(groups[1].replace(',', '')) if groups[1] else 0
            return eok_part * 100000000 + man_part * 10000
        
        elif pattern_type == 'korean_man':
            # X만원 format
            man_amount = int(groups[0].replace(',', ''))
            return man_amount * 10000
        
        elif pattern_type == 'korean_won':
            # X원 format
            return int(groups[0].replace(',', ''))
        
        elif pattern_type == 'number_only':
            # Plain number (assume won)
            return int(groups[0].replace(',', ''))
        
        else:
            raise ValueError(f"Unknown money pattern type: {pattern_type}")
    
    def _normalize_phone_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize phone number field"""
        for pattern, pattern_type in self.phone_patterns:
            match = re.search(pattern, value)
            if match:
                groups = match.groups()
                normalized_phone = '-'.join(groups)
                
                return NormalizedField(
                    field_name=field_name,
                    original_value=value,
                    normalized_value=normalized_phone,
                    data_type='phone',
                    confidence=0.9,
                    validation_status='valid',
                    evidence={
                        'pattern_type': pattern_type,
                        'match_groups': groups
                    },
                    validation_errors=[]
                )
        
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=value,
            data_type='phone',
            confidence=0.3,
            validation_status='warning',
            evidence={'no_phone_pattern_matched': True},
            validation_errors=["No phone pattern matched"]
        )
    
    def _normalize_registration_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize registration number field"""
        for pattern, pattern_type in self.registration_patterns:
            match = re.search(pattern, value)
            if match:
                number = match.group(1)
                
                return NormalizedField(
                    field_name=field_name,
                    original_value=value,
                    normalized_value=number,
                    data_type='registration_number',
                    confidence=0.9,
                    validation_status='valid',
                    evidence={
                        'pattern_type': pattern_type,
                        'extracted_number': number
                    },
                    validation_errors=[]
                )
        
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=value,
            data_type='registration_number',
            confidence=0.3,
            validation_status='warning',
            evidence={'no_registration_pattern_matched': True},
            validation_errors=["No registration pattern matched"]
        )
    
    def _normalize_text_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize text field"""
        # Basic text cleanup
        normalized_text = re.sub(r'\s+', ' ', value.strip())
        
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=normalized_text,
            data_type='text',
            confidence=0.8,
            validation_status='valid',
            evidence={'text_cleanup_applied': True},
            validation_errors=[]
        )
    
    def _normalize_generic_field(self, field_name: str, value: str) -> NormalizedField:
        """Normalize generic field"""
        return NormalizedField(
            field_name=field_name,
            original_value=value,
            normalized_value=value,
            data_type='generic',
            confidence=0.5,
            validation_status='valid',
            evidence={'no_specific_normalization': True},
            validation_errors=[]
        )
    
    def _run_validation_rules(self, normalized_fields: Dict[str, NormalizedField]):
        """Run cross-field validation rules"""
        for rule in self.validation_rules:
            # Check if all required fields are present
            required_fields = {field: normalized_fields.get(field) for field in rule.fields}
            
            if all(field is not None for field in required_fields.values()):
                try:
                    is_valid, error_message = rule.rule_function(required_fields)
                    
                    if not is_valid:
                        # Add validation error to relevant fields
                        for field in required_fields.values():
                            if field.validation_status == 'valid':
                                field.validation_status = rule.severity
                            field.validation_errors.append(f"{rule.rule_name}: {error_message}")
                            
                except Exception as e:
                    self.logger.warning(f"Validation rule {rule.rule_name} failed: {e}")
    
    def _validate_bid_schedule(self, fields: Dict[str, NormalizedField]) -> Tuple[bool, str]:
        """Validate bidding schedule logic"""
        bid_start = fields.get('bid_start')
        bid_end = fields.get('bid_end')
        opening_date = fields.get('opening_date')
        
        if not all(f and f.normalized_value for f in [bid_start, bid_end, opening_date]):
            return True, "Insufficient date information"
        
        start_date = bid_start.normalized_value
        end_date = bid_end.normalized_value
        open_date = opening_date.normalized_value
        
        if start_date >= end_date:
            return False, "Bid start date must be before end date"
        
        if end_date > open_date:
            return False, "Bid end date must be before or equal to opening date"
        
        return True, ""
    
    def _validate_deposit_calculation(self, fields: Dict[str, NormalizedField]) -> Tuple[bool, str]:
        """Validate bid deposit calculation"""
        minimum_bid = fields.get('minimum_bid')
        bid_deposit = fields.get('bid_deposit')
        deposit_rate = fields.get('deposit_rate')
        
        if not all(f and f.normalized_value for f in [minimum_bid, bid_deposit]):
            return True, "Insufficient deposit information"
        
        min_bid_amount = minimum_bid.normalized_value
        deposit_amount = bid_deposit.normalized_value
        
        # Common deposit rates in Korean auctions
        standard_rates = [0.1, 0.2, 0.3]  # 10%, 20%, 30%
        
        for rate in standard_rates:
            expected_deposit = int(min_bid_amount * rate)
            # Allow ±1 won difference for rounding
            if abs(deposit_amount - expected_deposit) <= 1:
                return True, ""
        
        return False, f"Deposit amount {deposit_amount} doesn't match standard rates of minimum bid {min_bid_amount}"
    
    def _validate_date_consistency(self, fields: Dict[str, NormalizedField]) -> Tuple[bool, str]:
        """Validate date format consistency"""
        date_fields = [f for f in fields.values() if f and f.data_type == 'datetime']
        
        if len(date_fields) < 2:
            return True, "Insufficient date fields for consistency check"
        
        # Check if all dates use similar formatting patterns
        pattern_types = [f.evidence.get('pattern_type') for f in date_fields]
        unique_patterns = set(pattern_types)
        
        if len(unique_patterns) > 2:
            return False, f"Inconsistent date patterns used: {unique_patterns}"
        
        return True, ""