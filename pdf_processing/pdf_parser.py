"""
PDF parsing module using PyMuPDF for text, table, and image extraction
"""
import os
import fitz  # PyMuPDF
import json
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from utils.logger import setup_logger


@dataclass
class TextBlock:
    """Represents a text block with positioning info"""
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    font_size: float
    font_name: str
    page_number: int


@dataclass
class TableData:
    """Represents table data"""
    data: List[List[str]]
    bbox: Tuple[float, float, float, float]
    row_count: int
    col_count: int
    page_number: int
    table_index: int


@dataclass
class ImageData:
    """Represents image data"""
    image_path: str
    bbox: Tuple[float, float, float, float]
    width: int
    height: int
    format_type: str
    file_size: int
    page_number: int
    image_index: int


class PDFParser:
    """PyMuPDF-based PDF parser for extracting text, tables, and images"""
    
    def __init__(self, output_dir: str = "extracted_images"):
        self.logger = setup_logger(__name__)
        self.output_dir = output_dir
        self._ensure_output_directory()
    
    def _ensure_output_directory(self):
        """Ensure output directory for images exists"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.logger.info(f"Created image output directory: {self.output_dir}")
    
    def parse_pdf(self, pdf_path: str, notice_id: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract all content
        
        Args:
            pdf_path: Path to PDF file
            notice_id: Notice ID for organizing output
            
        Returns:
            Dictionary containing extracted content
        """
        try:
            # Open PDF document
            doc = fitz.open(pdf_path)
            
            # Extract basic info
            pdf_info = {
                'file_path': pdf_path,
                'file_name': os.path.basename(pdf_path),
                'file_size': os.path.getsize(pdf_path),
                'page_count': doc.page_count,
                'notice_id': notice_id
            }
            
            # Extract content from all pages
            text_blocks = []
            tables = []
            images = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Extract text
                page_text_blocks = self._extract_text_from_page(page, page_num)
                text_blocks.extend(page_text_blocks)
                
                # Extract tables
                page_tables = self._extract_tables_from_page(page, page_num)
                tables.extend(page_tables)
                
                # Extract images
                page_images = self._extract_images_from_page(page, page_num, notice_id)
                images.extend(page_images)
            
            doc.close()
            
            result = {
                'pdf_info': pdf_info,
                'text_blocks': text_blocks,
                'tables': tables,
                'images': images,
                'statistics': {
                    'text_blocks_count': len(text_blocks),
                    'tables_count': len(tables),
                    'images_count': len(images)
                }
            }
            
            self.logger.info(
                f"Parsed PDF: {pdf_info['file_name']} - "
                f"{len(text_blocks)} text blocks, {len(tables)} tables, {len(images)} images"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse PDF {pdf_path}: {e}")
            return None
    
    def _extract_text_from_page(self, page: fitz.Page, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a page"""
        text_blocks = []
        
        try:
            # Get text blocks with detailed information
            blocks = page.get_text("dict")
            
            for block in blocks["blocks"]:
                if "lines" in block:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip():  # Non-empty text
                                text_block = TextBlock(
                                    text=span["text"],
                                    bbox=tuple(span["bbox"]),
                                    font_size=span["size"],
                                    font_name=span["font"],
                                    page_number=page_num + 1  # 1-indexed
                                )
                                text_blocks.append(text_block)
            
            self.logger.debug(f"Extracted {len(text_blocks)} text blocks from page {page_num + 1}")
            
        except Exception as e:
            self.logger.error(f"Failed to extract text from page {page_num + 1}: {e}")
        
        return text_blocks
    
    def _extract_tables_from_page(self, page: fitz.Page, page_num: int) -> List[TableData]:
        """Extract tables from a page using PyMuPDF's table detection"""
        tables = []
        
        try:
            # Find tables on the page
            table_tabs = page.find_tables()
            
            for table_index, table in enumerate(table_tabs):
                try:
                    # Extract table data
                    table_data = table.extract()
                    
                    if table_data and len(table_data) > 0:
                        # Clean table data - remove None values and convert to strings
                        cleaned_data = []
                        for row in table_data:
                            cleaned_row = []
                            for cell in row:
                                cell_value = str(cell) if cell is not None else ""
                                cleaned_row.append(cell_value.strip())
                            cleaned_data.append(cleaned_row)
                        
                        # Get table bounding box
                        bbox = table.bbox
                        
                        table_obj = TableData(
                            data=cleaned_data,
                            bbox=bbox,
                            row_count=len(cleaned_data),
                            col_count=len(cleaned_data[0]) if cleaned_data else 0,
                            page_number=page_num + 1,
                            table_index=table_index
                        )
                        
                        tables.append(table_obj)
                        
                        self.logger.debug(
                            f"Extracted table {table_index} from page {page_num + 1}: "
                            f"{table_obj.row_count}x{table_obj.col_count}"
                        )
                
                except Exception as e:
                    self.logger.warning(f"Failed to extract table {table_index} from page {page_num + 1}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Failed to find tables on page {page_num + 1}: {e}")
        
        return tables
    
    def _extract_images_from_page(self, page: fitz.Page, page_num: int, notice_id: str) -> List[ImageData]:
        """Extract images from a page"""
        images = []
        
        try:
            # Get list of images on the page
            image_list = page.get_images()
            
            for image_index, img in enumerate(image_list):
                try:
                    # Get image data
                    xref = img[0]
                    base_image = page.parent.extract_image(xref)
                    
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Create image filename
                    image_filename = f"notice_{notice_id}_page_{page_num + 1}_img_{image_index + 1}.{image_ext}"
                    image_path = os.path.join(self.output_dir, image_filename)
                    
                    # Save image file
                    with open(image_path, "wb") as image_file:
                        image_file.write(image_bytes)
                    
                    # Get image dimensions and other info
                    try:
                        with Image.open(image_path) as pil_image:
                            width, height = pil_image.size
                    except Exception:
                        # Fallback to PyMuPDF dimensions
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)
                    
                    # Get image position on page (approximate)
                    image_rects = page.get_image_rects(xref)
                    bbox = image_rects[0] if image_rects else (0, 0, width, height)
                    
                    image_data = ImageData(
                        image_path=image_path,
                        bbox=bbox,
                        width=width,
                        height=height,
                        format_type=image_ext,
                        file_size=len(image_bytes),
                        page_number=page_num + 1,
                        image_index=image_index
                    )
                    
                    images.append(image_data)
                    
                    self.logger.debug(
                        f"Extracted image {image_index} from page {page_num + 1}: "
                        f"{width}x{height} {image_ext}"
                    )
                
                except Exception as e:
                    self.logger.warning(f"Failed to extract image {image_index} from page {page_num + 1}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Failed to extract images from page {page_num + 1}: {e}")
        
        return images
    
    def get_pdf_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """Extract PDF metadata"""
        try:
            doc = fitz.open(pdf_path)
            metadata = doc.metadata
            
            # Add file information
            metadata.update({
                'file_size': os.path.getsize(pdf_path),
                'page_count': doc.page_count,
                'file_name': os.path.basename(pdf_path)
            })
            
            doc.close()
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to extract PDF metadata from {pdf_path}: {e}")
            return {}
    
    def extract_text_only(self, pdf_path: str) -> str:
        """Extract only text content from PDF (faster option)"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            
            for page in doc:
                text += page.get_text() + "\n\n"
            
            doc.close()
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
    
    def search_text_in_pdf(self, pdf_path: str, search_term: str) -> List[Dict[str, Any]]:
        """Search for specific text in PDF"""
        results = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text_instances = page.search_for(search_term)
                
                for instance in text_instances:
                    results.append({
                        'page_number': page_num + 1,
                        'bbox': tuple(instance),
                        'search_term': search_term,
                        'context': self._get_text_context(page, instance)
                    })
            
            doc.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search text in {pdf_path}: {e}")
            return []
    
    def _get_text_context(self, page: fitz.Page, bbox: fitz.Rect, context_margin: int = 50) -> str:
        """Get text context around a bounding box"""
        try:
            # Expand bounding box for context
            context_rect = fitz.Rect(
                bbox.x0 - context_margin,
                bbox.y0 - context_margin,
                bbox.x1 + context_margin,
                bbox.y1 + context_margin
            )
            
            # Clip to page boundaries
            context_rect &= page.rect
            
            # Get text in the context area
            context_text = page.get_textbox(context_rect)
            return context_text.strip()
            
        except Exception:
            return ""