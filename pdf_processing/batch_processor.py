"""
opendataloader-pdf 배치 변환 + notice_id 매핑.

다운로드 디렉토리(`downloads/notice_<id>_<title>/*.pdf`)를 스캔하여
한 번의 JVM 호출로 모든 PDF를 변환하고, 결과 JSON을 notice_id별로
PDFDocument 리스트로 분배한다.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import PDFDocument
from .opendataloader_adapter import OpenDataLoaderAdapter

NOTICE_DIR_PATTERN = re.compile(r"^notice_(?P<id>\d+)(?:_.*)?$")
STAGING_PREFIX = "notice"
STAGING_SEP = "__"


ConvertFn = Callable[..., None]


@dataclass
class NoticePDF:
    notice_id: str
    source_path: Path


@dataclass
class BatchResult:
    documents: Dict[str, List[PDFDocument]]
    failed: List[NoticePDF]


class BatchPDFConverter:
    """downloads/ 트리를 한 번에 opendataloader-pdf로 변환."""

    def __init__(
        self,
        downloads_dir: str | Path,
        output_dir: str | Path,
        *,
        convert_fn: Optional[ConvertFn] = None,
        adapter: Optional[OpenDataLoaderAdapter] = None,
        hybrid: Optional[str] = None,
        hybrid_url: Optional[str] = None,
        hybrid_fallback: bool = False,
        image_output: str = "off",
        keep_staging: bool = False,
    ) -> None:
        self.downloads_dir = Path(downloads_dir)
        self.output_dir = Path(output_dir)
        self.adapter = adapter or OpenDataLoaderAdapter()
        self.hybrid = hybrid
        self.hybrid_url = hybrid_url
        self.hybrid_fallback = hybrid_fallback
        self.image_output = image_output
        self.keep_staging = keep_staging
        self._convert_fn = convert_fn or self._default_convert_fn()

    @staticmethod
    def _default_convert_fn() -> ConvertFn:
        import opendataloader_pdf
        return opendataloader_pdf.convert

    def discover_pdfs(self) -> List[NoticePDF]:
        if not self.downloads_dir.exists():
            return []

        notices: List[NoticePDF] = []
        for child in sorted(self.downloads_dir.iterdir()):
            if not child.is_dir():
                continue
            match = NOTICE_DIR_PATTERN.match(child.name)
            if not match:
                continue
            notice_id = match.group("id")
            for pdf in sorted(child.glob("*.pdf")):
                notices.append(NoticePDF(notice_id=notice_id, source_path=pdf))
        return notices

    def _stage(self, pdfs: List[NoticePDF], staging_dir: Path) -> Dict[str, NoticePDF]:
        """staging_dir에 `{notice_id}__{idx}__{basename}` 형식으로 PDF 심볼릭 링크 생성."""
        staging_dir.mkdir(parents=True, exist_ok=True)
        mapping: Dict[str, NoticePDF] = {}
        for idx, item in enumerate(pdfs):
            staged_name = f"{STAGING_PREFIX}_{item.notice_id}{STAGING_SEP}{idx:04d}{STAGING_SEP}{item.source_path.name}"
            staged_path = staging_dir / staged_name
            if staged_path.exists() or staged_path.is_symlink():
                staged_path.unlink()
            try:
                staged_path.symlink_to(item.source_path.resolve())
            except (OSError, NotImplementedError):
                shutil.copy2(item.source_path, staged_path)
            mapping[staged_path.stem] = item
        return mapping

    @staticmethod
    def _extract_notice_id(staged_stem: str) -> Optional[str]:
        if not staged_stem.startswith(f"{STAGING_PREFIX}_"):
            return None
        remainder = staged_stem[len(STAGING_PREFIX) + 1:]
        parts = remainder.split(STAGING_SEP, 2)
        if not parts:
            return None
        return parts[0] if parts[0].isdigit() else None

    def convert(self, pdfs: List[NoticePDF]) -> BatchResult:
        documents: Dict[str, List[PDFDocument]] = {}
        failed: List[NoticePDF] = []

        if not pdfs:
            return BatchResult(documents=documents, failed=failed)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        staging_root = Path(tempfile.mkdtemp(prefix="odl_staging_"))
        try:
            mapping = self._stage(pdfs, staging_root)

            convert_kwargs = dict(
                input_path=str(staging_root),
                output_dir=str(self.output_dir),
                format="json",
                image_output=self.image_output,
                quiet=True,
            )
            if self.hybrid:
                convert_kwargs["hybrid"] = self.hybrid
            if self.hybrid_url:
                convert_kwargs["hybrid_url"] = self.hybrid_url
            if self.hybrid_fallback:
                convert_kwargs["hybrid_fallback"] = True

            self._convert_fn(**convert_kwargs)

            for staged_stem, notice_pdf in mapping.items():
                json_path = self.output_dir / f"{staged_stem}.json"
                if not json_path.exists():
                    failed.append(notice_pdf)
                    continue
                try:
                    doc = self.adapter.parse_file(json_path)
                    doc.file_name = notice_pdf.source_path.name
                    doc.metadata["notice_id"] = notice_pdf.notice_id
                    doc.metadata["source_path"] = str(notice_pdf.source_path)
                    documents.setdefault(notice_pdf.notice_id, []).append(doc)
                except Exception:
                    failed.append(notice_pdf)
        finally:
            if not self.keep_staging:
                shutil.rmtree(staging_root, ignore_errors=True)

        return BatchResult(documents=documents, failed=failed)

    def process_downloads(self) -> BatchResult:
        return self.convert(self.discover_pdfs())
