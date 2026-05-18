"""PDFPipeline 단위 테스트 (하이브리드 옵션 포함)."""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf_processing.batch_processor import BatchPDFConverter
from pdf_processing.pipeline import PDFPipeline, PipelineConfig

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n%dummy\n%%EOF")


class _FakeConverter:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        input_path = Path(kwargs["input_path"])
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        for pdf in input_path.glob("*.pdf"):
            shutil.copy(FIXTURES / "sample_text_pdf.json", output_dir / f"{pdf.stem}.json")


@pytest.fixture
def downloads(tmp_path: Path) -> Path:
    base = tmp_path / "downloads"
    _fake_pdf(base / "notice_500_test" / "01_t.pdf")
    return base


class TestPipelineConfig:
    def test_default_no_hybrid(self):
        config = PipelineConfig.from_module(SimpleNamespace())
        assert config.hybrid is None
        assert config.hybrid_fallback is False
        assert config.downloads_dir == "downloads"

    def test_reads_from_module(self):
        mod = SimpleNamespace(
            DOWNLOADS_DIR="custom_dl",
            PDF_OUTPUT_DIR="parsed",
            PDF_IMAGE_OUTPUT="external",
            PDF_IMAGE_DIR="imgs",
            PDF_HYBRID_MODE="docling-fast",
            PDF_HYBRID_URL="http://localhost:5002",
            PDF_HYBRID_FALLBACK=True,
        )
        config = PipelineConfig.from_module(mod)
        assert config.downloads_dir == "custom_dl"
        assert config.output_dir == "parsed"
        assert config.image_output == "external"
        assert config.image_dir == "imgs"
        assert config.hybrid == "docling-fast"
        assert config.hybrid_url == "http://localhost:5002"
        assert config.hybrid_fallback is True

    def test_real_config_module_loadable(self):
        import config as real_config
        result = PipelineConfig.from_module(real_config)
        assert result.downloads_dir == real_config.DOWNLOADS_DIR


class TestPipeline:
    def test_run_invokes_converter(self, downloads: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(downloads, tmp_path / "out", convert_fn=fake)
        pipeline = PDFPipeline(
            PipelineConfig(downloads_dir=str(downloads), output_dir=str(tmp_path / "out")),
            converter=converter,
        )
        result = pipeline.run()
        assert "500" in result.documents
        assert len(fake.calls) == 1

    def test_hybrid_options_propagate(self, downloads: Path, tmp_path: Path):
        fake = _FakeConverter()
        config = PipelineConfig(
            downloads_dir=str(downloads),
            output_dir=str(tmp_path / "out"),
            hybrid="docling-fast",
            hybrid_url="http://localhost:5002",
            hybrid_fallback=True,
        )
        # _build_converter() 경로를 직접 검증
        pipeline = PDFPipeline(config)
        pipeline.converter._convert_fn = fake  # 실제 호출 대신 fake로 교체
        pipeline.run()
        call = fake.calls[0]
        assert call["hybrid"] == "docling-fast"
        assert call["hybrid_url"] == "http://localhost:5002"
        assert call["hybrid_fallback"] is True

    def test_hybrid_disabled_by_default(self, downloads: Path, tmp_path: Path):
        fake = _FakeConverter()
        config = PipelineConfig(
            downloads_dir=str(downloads), output_dir=str(tmp_path / "out")
        )
        pipeline = PDFPipeline(config)
        pipeline.converter._convert_fn = fake
        pipeline.run()
        call = fake.calls[0]
        assert "hybrid" not in call
        assert "hybrid_url" not in call
        assert "hybrid_fallback" not in call

    def test_from_config_module(self, downloads: Path, monkeypatch):
        import config as real_config
        monkeypatch.setattr(real_config, "DOWNLOADS_DIR", str(downloads))
        pipeline = PDFPipeline.from_config_module(real_config)
        assert isinstance(pipeline.converter, BatchPDFConverter)
        assert str(pipeline.converter.downloads_dir) == str(downloads)
