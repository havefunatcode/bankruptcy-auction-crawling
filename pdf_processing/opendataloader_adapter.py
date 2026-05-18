"""
opendataloader-pdf JSON 출력을 PDFDocument 도메인 모델로 변환하는 어댑터.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import (
    BBox,
    ImageElement,
    PDFDocument,
    TableElement,
    TextElement,
)


TEXT_TYPES = frozenset({"paragraph", "heading", "caption", "header", "footer"})


class OpenDataLoaderAdapter:
    """opendataloader-pdf JSON → PDFDocument 변환."""

    def parse_file(self, json_path: str | Path) -> PDFDocument:
        path = Path(json_path)
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return self.parse_dict(data)

    def parse_dict(self, data: Dict[str, Any]) -> PDFDocument:
        file_name = data.get("file name", "")
        page_count = int(data.get("number of pages") or data.get("page count") or 0)

        metadata = {
            "author": data.get("author"),
            "title": data.get("title"),
            "creation_date": data.get("creation date"),
            "modification_date": data.get("modification date"),
        }

        document = PDFDocument(
            file_name=file_name,
            page_count=page_count,
            metadata=metadata,
        )

        table_counter = [0]
        image_counter = [0]
        for element in data.get("kids", []) or []:
            self._walk(element, document, table_counter, image_counter)

        return document

    def _walk(
        self,
        node: Dict[str, Any],
        document: PDFDocument,
        table_counter: List[int],
        image_counter: List[int],
        *,
        inside_table: bool = False,
    ) -> None:
        node_type = (node.get("type") or "").lower()

        if node_type == "table":
            table_counter[0] += 1
            table = self._build_table(node, table_index=table_counter[0] - 1)
            if table is not None:
                document.tables.append(table)
            return

        if node_type == "image":
            image_counter[0] += 1
            document.images.append(
                ImageElement(
                    bbox=_parse_bbox(node.get("bounding box")),
                    page_number=int(node.get("page number") or 0),
                    image_index=image_counter[0] - 1,
                    image_path=node.get("path"),
                )
            )
            return

        if node_type in TEXT_TYPES and not inside_table:
            content = (node.get("content") or "").strip()
            if content:
                document.text_elements.append(
                    TextElement(
                        text=content,
                        bbox=_parse_bbox(node.get("bounding box")),
                        page_number=int(node.get("page number") or 0),
                        element_type=node_type,
                        font=node.get("font"),
                        font_size=_safe_float(node.get("font size")),
                        heading_level=_safe_int(node.get("heading level")),
                    )
                )

        for child in node.get("kids", []) or []:
            self._walk(
                child,
                document,
                table_counter,
                image_counter,
                inside_table=inside_table,
            )

    def _build_table(self, node: Dict[str, Any], *, table_index: int) -> Optional[TableElement]:
        rows = node.get("rows") or []
        row_count = int(node.get("number of rows") or len(rows))
        col_count = int(node.get("number of columns") or 0)

        if not rows and not (row_count and col_count):
            return None

        if not col_count and rows:
            col_count = max(
                (len(r.get("cells") or []) for r in rows),
                default=0,
            )

        matrix: List[List[str]] = [["" for _ in range(col_count)] for _ in range(row_count)]
        for r_idx, row in enumerate(rows):
            for cell in row.get("cells") or []:
                rn = int(cell.get("row number") or (r_idx + 1)) - 1
                cn = int(cell.get("column number") or 1) - 1
                if 0 <= rn < row_count and 0 <= cn < col_count:
                    matrix[rn][cn] = _cell_text(cell)

        return TableElement(
            data=matrix,
            bbox=_parse_bbox(node.get("bounding box")),
            row_count=row_count,
            col_count=col_count,
            page_number=int(node.get("page number") or 0),
            table_index=table_index,
        )


def _cell_text(cell: Dict[str, Any]) -> str:
    parts: List[str] = []

    def collect(items: Iterable[Dict[str, Any]]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            content = (item.get("content") or "").strip()
            if content:
                parts.append(content)
            children = item.get("kids") or []
            if children:
                collect(children)

    collect(cell.get("kids") or [])
    return " ".join(parts).strip()


def _parse_bbox(value: Any) -> BBox:
    if not value or not isinstance(value, (list, tuple)) or len(value) < 4:
        return (0.0, 0.0, 0.0, 0.0)
    return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
