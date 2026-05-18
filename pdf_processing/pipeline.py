"""
PDF 처리 파이프라인.

config.py의 설정을 읽어 BatchPDFConverter를 구성하고,
다운로드 디렉토리 전체를 한 번에 변환한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .batch_processor import BatchPDFConverter, BatchResult


@dataclass
class PipelineConfig:
    downloads_dir: str = "downloads"
    output_dir: str = "parsed_pdfs"
    image_output: str = "off"
    image_dir: str = "extracted_images"
    hybrid: Optional[str] = None
    hybrid_url: Optional[str] = None
    hybrid_fallback: bool = False

    @classmethod
    def from_module(cls, module) -> "PipelineConfig":
        """config.py 모듈로부터 PipelineConfig 생성."""
        return cls(
            downloads_dir=getattr(module, "DOWNLOADS_DIR", "downloads"),
            output_dir=getattr(module, "PDF_OUTPUT_DIR", "parsed_pdfs"),
            image_output=getattr(module, "PDF_IMAGE_OUTPUT", "off"),
            image_dir=getattr(module, "PDF_IMAGE_DIR", "extracted_images"),
            hybrid=getattr(module, "PDF_HYBRID_MODE", None),
            hybrid_url=getattr(module, "PDF_HYBRID_URL", None),
            hybrid_fallback=getattr(module, "PDF_HYBRID_FALLBACK", False),
        )


class PDFPipeline:
    """전체 PDF 처리 파이프라인 진입점."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        converter: Optional[BatchPDFConverter] = None,
    ) -> None:
        self.config = config
        self.converter = converter or self._build_converter()

    def _build_converter(self) -> BatchPDFConverter:
        kwargs: dict = {
            "image_output": self.config.image_output,
        }
        if self.config.hybrid:
            kwargs["hybrid"] = self.config.hybrid
            kwargs["hybrid_fallback"] = self.config.hybrid_fallback
            if self.config.hybrid_url:
                kwargs["hybrid_url"] = self.config.hybrid_url
        return BatchPDFConverter(
            downloads_dir=self.config.downloads_dir,
            output_dir=self.config.output_dir,
            **kwargs,
        )

    def run(self) -> BatchResult:
        return self.converter.process_downloads()

    @classmethod
    def from_config_module(cls, module) -> "PDFPipeline":
        return cls(PipelineConfig.from_module(module))
