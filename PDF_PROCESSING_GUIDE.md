# PDF Processing Guide

PyMuPDF를 사용한 PDF 텍스트/테이블/이미지 추출 및 PostgreSQL 저장 가이드

## 🛠️ 설치 및 설정

### 1. 의존성 설치
```bash
# 가상환경 활성화
source venv/bin/activate

# 의존성 설치 (PyMuPDF, psycopg2, Pillow 포함)
pip install -r requirements.txt
```

### 2. PostgreSQL 설정 (Docker)
```bash
# PostgreSQL Docker 컨테이너 실행 (포트 5432)
docker run --name bankruptcy-postgres \
    -e POSTGRES_DB=bankruptcy_auction \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -p 5432:5432 \
    -d postgres:15

# 또는 기존 컨테이너가 있다면
docker start bankruptcy-postgres
```

### 3. 환경변수 설정 (선택사항)
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=bankruptcy_auction
export DB_USER=postgres
export DB_PASSWORD=postgres
```

## 🚀 사용법

### 1. 메인 크롤러와 통합 사용

#### PDF 처리를 포함한 전체 크롤링
```bash
# 첨부파일 다운로드 + PDF 처리 + DB 저장
python main.py --with-attachments --process-pdfs --max-pages 2

# 헤드리스 모드 비활성화 (브라우저 보기)
python main.py --with-attachments --process-pdfs --headless --max-pages 1
```

#### PDF 처리 없이 크롤링만
```bash
# 첨부파일 다운로드만 (PDF 처리 안함)
python main.py --with-attachments --no-pdf-processing --max-pages 1
```

### 2. 독립적인 PDF 처리

#### 기존 다운로드된 PDF 파일들 처리
```bash
# 전체 PDF 처리
python process_pdfs.py

# 특정 공고의 PDF만 처리
python process_pdfs.py --notice-id 405

# 최대 10개 파일만 처리
python process_pdfs.py --max-files 10

# 비동기 처리 (더 빠름)
python process_pdfs.py --async --concurrent 5
```

#### 데이터베이스 작업
```bash
# DB 연결 테스트
python process_pdfs.py --test-db

# DB 스키마 초기화
python process_pdfs.py --init-db

# 처리 요약 보기
python process_pdfs.py --summary

# PDF 내용 검색
python process_pdfs.py --search "매각"
```

### 3. 테스트 및 검증
```bash
# 전체 구현 테스트
python test_pdf_implementation.py
```

## 📊 데이터베이스 구조

### 주요 테이블
- **pdf_documents**: PDF 파일 메타데이터
- **pdf_text_content**: 추출된 텍스트 (위치 정보 포함)
- **pdf_tables**: 테이블 데이터 (JSON 형태)
- **pdf_images**: 이미지 정보 및 파일 경로

### 데이터 조회 예시
```sql
-- 처리 요약 보기
SELECT * FROM pdf_processing_summary;

-- 텍스트 검색 (한국어 전문검색 지원)
SELECT pd.notice_id, pd.file_name, ptc.text_content 
FROM pdf_text_content ptc
JOIN pdf_documents pd ON ptc.document_id = pd.id
WHERE to_tsvector('korean', ptc.text_content) @@ plainto_tsquery('korean', '매각');

-- 테이블 데이터 조회
SELECT notice_id, file_name, page_number, table_data
FROM pdf_tables pt
JOIN pdf_documents pd ON pt.document_id = pd.id;
```

## 📁 출력 구조

### 파일 저장 위치
```
downloads/                          # 원본 PDF 파일
├── notice_405_공고제목/
│   └── 01_파일명.pdf

extracted_images/                   # 추출된 이미지
├── notice_405_page_1_img_1.png
└── notice_405_page_2_img_1.jpg

output/                             # 크롤링 결과
├── bankruptcy_auctions_날짜시간.csv
└── bankruptcy_auctions_날짜시간_summary.txt
```

### 추출 가능한 데이터
- **텍스트**: 폰트, 크기, 위치 정보 포함
- **테이블**: 행/열 구조를 유지한 JSON 데이터
- **이미지**: PNG/JPG 파일로 저장, 크기/위치 정보

## ⚙️ 설정 옵션

### config.py 주요 설정
```python
# PDF 처리 활성화
PROCESS_PDFS = True
PDF_PROCESSING_ENABLED = True

# 이미지 저장 디렉토리
EXTRACTED_IMAGES_DIR = "extracted_images"

# 데이터베이스 설정
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "bankruptcy_auction"
```

## 🔧 문제 해결

### 일반적인 오류
1. **Database connection failed**
   - Docker PostgreSQL 컨테이너가 실행 중인지 확인
   - 포트 5432가 사용 중인지 확인

2. **PyMuPDF import error**
   - `pip install PyMuPDF>=1.23.0` 재설치

3. **Permission denied**
   - extracted_images, logs 디렉토리 쓰기 권한 확인

### 성능 최적화
- 비동기 처리 사용: `--async --concurrent 5`
- 배치 크기 제한: `--max-files 50`
- Docker PostgreSQL 메모리 설정 증가

## 📝 예제 워크플로우

### 1. 초기 설정
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. PostgreSQL 실행
docker run --name bankruptcy-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15

# 3. DB 테스트
python process_pdfs.py --test-db --init-db
```

### 2. 데이터 수집 및 처리
```bash
# 1. 크롤링 + 첨부파일 다운로드 + PDF 처리
python main.py --with-attachments --process-pdfs --max-pages 3

# 2. 결과 확인
python process_pdfs.py --summary

# 3. 검색 테스트
python process_pdfs.py --search "부동산"
```

### 3. 기존 파일 일괄 처리
```bash
# 이미 다운로드된 PDF들을 일괄 처리
python process_pdfs.py --async --concurrent 3
```

## 🎯 활용 사례

- **법률 문서 분석**: 파산경매 공고 내용 자동 분석
- **데이터 마이닝**: 공고 패턴 및 트렌드 분석  
- **검색 시스템**: 한국어 전문검색 지원
- **자동화**: 신규 공고 자동 처리 및 알림