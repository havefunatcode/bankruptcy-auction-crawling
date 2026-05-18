# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

### Initial Setup
```bash
# Java 11+ 필요 (opendataloader-pdf JVM 런타임)
java -version

# Python 가상환경
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 의존성 설치
pip install -r requirements.txt
playwright install

# 동작 확인
python main.py --preview
python -m pytest tests/
```

### Development Workflow
```bash
source venv/bin/activate

# 목록만 크롤링
python main.py --no-attachments --max-pages 1

# 첨부파일 + PDF 처리
python main.py --with-attachments --process-pdfs --max-pages 2

# 헤드풀 디버그
python main.py --headless false --max-pages 1

# PDF만 일괄 변환 (이미 다운로드된 PDF)
python process_pdfs.py
python process_pdfs.py --hybrid docling-fast --hybrid-fallback
python process_pdfs.py --store-db
```

## Architecture Overview

한국 대법원 파산자 공매 공고를 비동기 크롤링하고, PDF는 **opendataloader-pdf** (Java 기반, Apache 2.0, 추출 정확도 벤치마크 #1)로 구조화 데이터를 추출한다.

### 두 단계 처리
1. **크롤링 단계**: Playwright로 목록·상세·첨부파일 수집 → `downloads/notice_<id>_<title>/`에 PDF 저장
2. **PDF 추출 단계**: `opendataloader-pdf`가 단일 JVM 호출로 디렉토리를 일괄 변환 → JSON/Markdown 출력 → `PDFDocument` 도메인 모델로 어댑팅 → MySQL 영속화

### Core Modules

**크롤러 (`crawler/`)**
- `browser_controller.py` — Playwright 세션, 더블클릭 fallback 등
- `data_extractor.py` / `detail_extractor.py` — 목록·상세 HTML 파싱
- `attachment_downloader.py` — JS 함수 / 직접 링크 양쪽 처리
- `pagination_handler.py` — 목록 전용 크롤링
- `enhanced_pagination_handler.py` — 상세 + 첨부 + PDF 처리

**PDF 파이프라인 (`pdf_processing/`)**
- `models.py` — `PDFDocument`, `TextElement`, `TableElement`, `ImageElement`
- `opendataloader_adapter.py` — opendataloader JSON → 도메인 모델
- `batch_processor.py` — 다운로드 디렉토리 → 단일 JVM 배치 변환, notice_id 매핑
- `pipeline.py` — `PipelineConfig` + `PDFPipeline` (config 기반 진입점)
- `persistence.py` — `PDFDocumentRepository` (PDFDocument → DB)

**DB (`database/`)** — MySQL 8.0+
- `database_manager.py` — PyMySQL 기반 저수준 CRUD
- `schema.sql` — `pdf_documents` / `pdf_text_content` / `pdf_tables` / `pdf_images` + ngram 파서 FULLTEXT

### Why opendataloader-pdf
- 테이블 추출 정확도 0.928 (PyMuPDF 대비 큰 폭 상승), 한국어 OCR 80+ 언어 지원
- XY-Cut++ 읽기 순서 → 다단 공고문 안정적
- bounding box + 의미 타입(heading/paragraph/table/caption) 직접 제공
- JVM 호출 비용이 있으므로 **반드시 배치 호출**해야 함 — `BatchPDFConverter`가 staging 디렉토리로 한 번에 묶어 처리

### Hybrid (AI) Mode
스캔본/복잡한 테이블에 대해 `config.PDF_HYBRID_MODE = "docling-fast"`로 활성화. 별도 데몬 실행 필요:
```bash
pip install "opendataloader-pdf[hybrid]"
opendataloader-pdf-hybrid --port 5002 --force-ocr --ocr-lang ko,en
```

## Configuration (`config.py`)
- `DELAY_BETWEEN_REQUESTS`, `MAX_RETRIES` — 크롤링 속도 제한
- `DOWNLOAD_ATTACHMENTS`, `DOWNLOADS_DIR`, `ALLOWED_EXTENSIONS`
- `PROCESS_PDFS`, `PDF_PROCESSING_ENABLED`
- `PDF_OUTPUT_DIR`, `PDF_IMAGE_OUTPUT`, `PDF_IMAGE_DIR`
- `PDF_HYBRID_MODE`, `PDF_HYBRID_URL`, `PDF_HYBRID_FALLBACK`
- `DB_*` — MySQL 연결 (DB_HOST, DB_PORT=3306, DB_USER, DB_PASSWORD, DB_NAME, DB_CHARSET=utf8mb4)

## Output Structure
```
output/                          # 크롤링 결과 CSV/JSON
downloads/notice_<id>_<title>/   # 다운로드된 PDF
parsed_pdfs/                     # opendataloader-pdf JSON 출력 (.gitignored)
extracted_images/                # PDF에서 추출된 이미지 (옵션)
logs/                            # 실행 로그
```

## Testing
```bash
# 전체 단위 테스트 (빠름, JVM 없이도 동작)
python -m pytest tests/

# 통합 테스트(실제 JVM 호출 포함) 제외
python -m pytest tests/ -m "not integration"

# 통합만
python -m pytest tests/ -m integration
```

## Debugging
- 크롤러 로그: `logs/` 디렉토리
- PDF 변환 확인: `python process_pdfs.py --downloads-dir downloads --output-dir /tmp/odl`
- DB 연결: `python process_pdfs.py --test-db`
- 헤드풀 브라우저: `python main.py --headless false`
