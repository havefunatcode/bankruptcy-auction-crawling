# Bankruptcy Auction Crawler

한국 대법원 파산자 공매 공고 크롤러 + opendataloader-pdf 기반 PDF 추출 파이프라인.

## 주요 기능

- **공고 크롤링** — Playwright 비동기 크롤러로 목록·상세·첨부파일 수집
- **첨부파일 자동 다운로드** — JS 함수 / 직접 링크 모두 처리, 공고별 폴더로 정리
- **PDF 추출** — [opendataloader-pdf](https://github.com/opendataloader-project/opendataloader-pdf) (Java, Apache 2.0)로 텍스트·테이블·이미지를 bounding box와 함께 추출
- **하이브리드 OCR** — 스캔본·복잡한 테이블은 별도 AI 백엔드로 위임 (선택)
- **PostgreSQL 영속화** — `PDFDocument` 단위 트랜잭션으로 저장
- **CSV/JSON 출력** — 크롤링 결과를 다양한 포맷으로 저장

## 사전 요구사항

- Python 3.10+
- **Java 11+** (opendataloader-pdf JVM 런타임 — [Adoptium](https://adoptium.net/) 설치)
- PostgreSQL 14+ (DB 저장이 필요한 경우, Docker 사용 가능)

## 설치

```bash
git clone https://github.com/havefunatcode/bankruptcy-auction-crawling.git
cd bankruptcy-auction-crawling

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
playwright install

# Java 확인
java -version

# 동작 확인
python main.py --preview
```

### 하이브리드 모드 (선택)

스캔본 PDF나 복잡한 테이블의 추출 품질을 높이려면 하이브리드 백엔드를 사용한다.

```bash
pip install "opendataloader-pdf[hybrid]"

# 별도 터미널에서 실행
opendataloader-pdf-hybrid --port 5002 --force-ocr --ocr-lang ko,en

# config.py
# PDF_HYBRID_MODE = "docling-fast"
# PDF_HYBRID_FALLBACK = True
```

## 사용법

### 크롤러
```bash
# 미리보기 (페이지 범위 확인)
python main.py --preview

# 목록만
python main.py --no-attachments --max-pages 3

# 첨부파일 + PDF 추출 동시 처리
python main.py --with-attachments --process-pdfs --max-pages 2

# 특정 페이지
python main.py --pages 1 5 10

# 디버그 (헤드풀)
python main.py --headless false --max-pages 1
```

### PDF 일괄 처리 (이미 다운로드된 PDF에 대해)
```bash
# 기본: downloads/ 전체를 parsed_pdfs/에 JSON으로 출력
python process_pdfs.py

# 하이브리드 모드
python process_pdfs.py --hybrid docling-fast --hybrid-fallback

# DB 저장 포함
python process_pdfs.py --store-db

# DB 연결 테스트 / 스키마 초기화
python process_pdfs.py --test-db
python process_pdfs.py --init-db
```

## 출력 구조

```
output/                          # 크롤링 결과
  bankruptcy_auctions_*.csv
  bankruptcy_auctions_*_summary.txt
  attachment_summary_*.json

downloads/                       # 다운로드된 첨부파일
  notice_405_공고제목/
    01_첨부파일.pdf

parsed_pdfs/                     # opendataloader-pdf JSON (.gitignored)
  notice_405__0000__01_첨부파일.json
```

## 프로젝트 구조

```
bankruptcy-auction-crawling/
├── config.py                       # 환경 설정
├── main.py                         # 크롤러 진입점
├── process_pdfs.py                 # PDF 일괄 처리 CLI
├── crawler/                        # 크롤러 모듈
│   ├── browser_controller.py
│   ├── data_extractor.py
│   ├── detail_extractor.py
│   ├── attachment_downloader.py
│   ├── pagination_handler.py
│   ├── enhanced_pagination_handler.py
│   └── data_storage.py
├── pdf_processing/                 # PDF 추출 파이프라인
│   ├── models.py                   # PDFDocument, TextElement, ...
│   ├── opendataloader_adapter.py   # JSON → 도메인 모델
│   ├── batch_processor.py          # 단일 JVM 배치 변환
│   ├── pipeline.py                 # PipelineConfig + PDFPipeline
│   └── persistence.py              # PDFDocumentRepository
├── database/                       # PostgreSQL 계층
│   ├── database_manager.py
│   ├── config_db.py
│   └── schema.sql
├── utils/                          # 공통 유틸
└── tests/                          # pytest 단위·통합 테스트
```

## 테스트

```bash
# 전체 (단위 + 통합)
python -m pytest tests/ -v

# 단위만 (JVM 없이도 동작)
python -m pytest tests/ -m "not integration"
```

46개 테스트 케이스 (어댑터·배치·파이프라인·영속화 + 실제 JVM 통합).

## 주의사항

- 사이트 부담을 줄이기 위해 `DELAY_BETWEEN_REQUESTS=2.0`초 유지를 권장
- opendataloader-pdf는 JVM 시작 비용이 있으므로 **공고별 호출 금지** — `BatchPDFConverter`가 한 번에 처리
- 한국어 스캔 PDF는 하이브리드 모드 권장 (로컬 모드는 이미지로만 인식됨)
- 사이트 구조 변경 시 `crawler/browser_controller.py`, `crawler/data_extractor.py`의 셀렉터 수정 필요

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다. 의존 라이브러리는 모두 Apache 2.0 / MIT 호환.
