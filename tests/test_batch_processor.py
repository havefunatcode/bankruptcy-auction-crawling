"""BatchPDFConverter 단위·통합 테스트."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pdf_processing.batch_processor import BatchPDFConverter, NoticePDF

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n%dummy\n%%EOF")


def _fixture_json(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return json.load(f)


class _FakeConverter:
    """opendataloader_pdf.convert() 대체. staging의 PDF별로 fixture JSON을 복사."""

    def __init__(self, fixture_map: dict[str, str] | None = None, fail_for: set[str] | None = None):
        self.fixture_map = fixture_map or {}
        self.fail_for = fail_for or set()
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> None:
        self.calls.append(kwargs)
        input_path = Path(kwargs["input_path"])
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        for pdf in input_path.glob("*.pdf"):
            if pdf.stem in self.fail_for:
                continue
            fixture_name = self.fixture_map.get(pdf.stem, "sample_text_pdf.json")
            shutil.copy(FIXTURES / fixture_name, output_dir / f"{pdf.stem}.json")


@pytest.fixture
def downloads_tree(tmp_path: Path) -> Path:
    base = tmp_path / "downloads"
    _fake_pdf(base / "notice_378_매각공고" / "01_first.pdf")
    _fake_pdf(base / "notice_379_자산매각" / "01_second.pdf")
    _fake_pdf(base / "notice_379_자산매각" / "02_appendix.pdf")
    _fake_pdf(base / "random_dir" / "ignored.pdf")  # 패턴 미일치
    return base


class TestDiscovery:
    def test_finds_notices(self, downloads_tree: Path):
        converter = BatchPDFConverter(downloads_tree, downloads_tree.parent / "out")
        pdfs = converter.discover_pdfs()
        notice_ids = sorted({p.notice_id for p in pdfs})
        assert notice_ids == ["378", "379"]
        assert len(pdfs) == 3

    def test_ignores_non_notice_dirs(self, downloads_tree: Path):
        converter = BatchPDFConverter(downloads_tree, downloads_tree.parent / "out")
        pdfs = converter.discover_pdfs()
        assert all("random_dir" not in str(p.source_path) for p in pdfs)

    def test_empty_downloads(self, tmp_path: Path):
        converter = BatchPDFConverter(tmp_path / "empty", tmp_path / "out")
        assert converter.discover_pdfs() == []

    def test_missing_downloads_dir(self, tmp_path: Path):
        converter = BatchPDFConverter(tmp_path / "nope", tmp_path / "out")
        assert converter.discover_pdfs() == []


class TestConvert:
    def test_groups_by_notice_id(self, downloads_tree: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        result = converter.process_downloads()
        assert set(result.documents.keys()) == {"378", "379"}
        assert len(result.documents["378"]) == 1
        assert len(result.documents["379"]) == 2
        assert result.failed == []

    def test_single_jvm_call_for_batch(self, downloads_tree: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        converter.process_downloads()
        assert len(fake.calls) == 1, "JVM 시작 비용을 줄이려면 단 1회 호출되어야 함"

    def test_attaches_notice_metadata(self, downloads_tree: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        result = converter.process_downloads()
        for notice_id, docs in result.documents.items():
            for doc in docs:
                assert doc.metadata["notice_id"] == notice_id
                assert doc.metadata["source_path"].endswith(".pdf")
                assert doc.file_name.endswith(".pdf")

    def test_records_failures(self, downloads_tree: Path, tmp_path: Path):
        # 모든 staging PDF를 실패시켜 모두 failed 리스트에 들어가는지 검증
        class FailingConverter:
            def __init__(self):
                self.calls = []

            def __call__(self, **kwargs):
                self.calls.append(kwargs)
                # 출력 파일 생성하지 않음 → 매핑 실패 처리

        fake = FailingConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        result = converter.process_downloads()
        assert len(result.failed) == 3
        assert result.documents == {}

    def test_partial_failure(self, downloads_tree: Path, tmp_path: Path):
        # staging 단계에서 파일명에 idx가 들어가므로 stem 매칭으로 실패 시뮬레이션
        all_stems_first_call: list[str] = []

        class SelectiveConverter:
            def __init__(self):
                self.calls = []

            def __call__(self, **kwargs):
                self.calls.append(kwargs)
                input_path = Path(kwargs["input_path"])
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                stems = sorted(p.stem for p in input_path.glob("*.pdf"))
                all_stems_first_call.extend(stems)
                # 두 번째 PDF만 실패시킴
                for stem in stems[:1] + stems[2:]:
                    shutil.copy(FIXTURES / "sample_text_pdf.json", output_dir / f"{stem}.json")

        fake = SelectiveConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        result = converter.process_downloads()
        total_docs = sum(len(v) for v in result.documents.values())
        assert total_docs == 2
        assert len(result.failed) == 1

    def test_passes_hybrid_options(self, downloads_tree: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out",
            convert_fn=fake,
            hybrid="docling-fast",
            hybrid_url="http://localhost:5002",
            hybrid_fallback=True,
        )
        converter.process_downloads()
        call = fake.calls[0]
        assert call["hybrid"] == "docling-fast"
        assert call["hybrid_url"] == "http://localhost:5002"
        assert call["hybrid_fallback"] is True

    def test_default_no_hybrid_kwargs(self, downloads_tree: Path, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        converter.process_downloads()
        call = fake.calls[0]
        assert "hybrid" not in call
        assert "hybrid_url" not in call

    def test_staging_cleaned_up(self, downloads_tree: Path, tmp_path: Path):
        seen_input_paths: list[str] = []

        class TrackingConverter(_FakeConverter):
            def __call__(self, **kwargs):
                seen_input_paths.append(kwargs["input_path"])
                super().__call__(**kwargs)

        fake = TrackingConverter()
        converter = BatchPDFConverter(
            downloads_tree, tmp_path / "out", convert_fn=fake
        )
        converter.process_downloads()
        assert seen_input_paths
        assert not Path(seen_input_paths[0]).exists(), "staging 디렉토리가 정리되어야 함"

    def test_empty_input_short_circuits(self, tmp_path: Path):
        fake = _FakeConverter()
        converter = BatchPDFConverter(
            tmp_path / "empty", tmp_path / "out", convert_fn=fake
        )
        result = converter.convert([])
        assert result.documents == {}
        assert result.failed == []
        assert fake.calls == []


@pytest.mark.integration
class TestRealConversion:
    """실제 opendataloader-pdf 호출 통합 테스트 (Java 필요, 느림)."""

    def test_real_pdf_roundtrip(self, tmp_path: Path):
        pytest.importorskip("opendataloader_pdf")

        real_pdf = next(
            (
                p for p in Path("downloads").rglob("*.pdf")
                if p.stat().st_size < 2_000_000
            ),
            None,
        )
        if real_pdf is None:
            pytest.skip("downloads/ 아래에 통합 테스트용 PDF가 없음")

        notice_match = next(
            (
                m for m in [
                    __import__("re").match(r"notice_(\d+)", part)
                    for part in real_pdf.parts
                ] if m
            ),
            None,
        )
        if notice_match is None:
            pytest.skip("PDF가 notice_<id> 디렉토리에 없음")
        notice_id = notice_match.group(1)

        staged = tmp_path / "downloads" / f"notice_{notice_id}_test"
        staged.mkdir(parents=True)
        shutil.copy(real_pdf, staged / real_pdf.name)

        converter = BatchPDFConverter(
            tmp_path / "downloads", tmp_path / "out"
        )
        result = converter.process_downloads()
        assert notice_id in result.documents
        assert len(result.documents[notice_id]) == 1
        doc = result.documents[notice_id][0]
        assert doc.page_count > 0
