"""
PDF 추출 도메인 모델.

opendataloader-pdf JSON 출력을 정규화한 데이터 구조.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any


BBox = Tuple[float, float, float, float]  # [left, bottom, right, top]


@dataclass
class TextElement:
    text: str
    bbox: BBox
    page_number: int
    element_type: str
    font: Optional[str] = None
    font_size: Optional[float] = None
    heading_level: Optional[int] = None


@dataclass
class TableElement:
    data: List[List[str]]
    bbox: BBox
    row_count: int
    col_count: int
    page_number: int
    table_index: int


@dataclass
class ImageElement:
    bbox: BBox
    page_number: int
    image_index: int
    image_path: Optional[str] = None


@dataclass
class PDFDocument:
    file_name: str
    page_count: int
    text_elements: List[TextElement] = field(default_factory=list)
    tables: List[TableElement] = field(default_factory=list)
    images: List[ImageElement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        ordered = sorted(
            self.text_elements,
            key=lambda e: (e.page_number, -e.bbox[3], e.bbox[0]),
        )
        return "\n".join(e.text for e in ordered if e.text)

    @property
    def headings(self) -> List[TextElement]:
        return [e for e in self.text_elements if e.element_type == "heading"]

    @property
    def paragraphs(self) -> List[TextElement]:
        return [e for e in self.text_elements if e.element_type == "paragraph"]
