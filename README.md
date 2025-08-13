# Bankruptcy Auction Crawler

한국 대법원 파산자 공매 정보 크롤러입니다.

## 개요

이 프로젝트는 https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work 사이트에서 파산자 공매 정보를 자동으로 수집하는 Python 크롤러입니다.

## 주요 기능

- **자동 페이지 탐색**: 첫 페이지부터 마지막 페이지까지 자동으로 탐색
- **데이터 추출**: 파산자 공매 정보 (관할청, 사건번호, 제목, 조회수 등) 추출
- **첨부파일 다운로드**: 각 공고의 상세 페이지에서 PDF, DOC, HWP 등 첨부파일 자동 다운로드
- **상세 정보 수집**: 공고 상세 내용, 연락처, 마감일자 등 세부 정보 추출
- **다중 포맷 지원**: CSV, JSON 형식으로 데이터 저장
- **오류 처리**: 강력한 재시도 로직과 오류 복구 메커니즘
- **속도 제한**: 웹사이트에 부담을 주지 않는 적절한 속도 제한
- **미리보기 모드**: 실제 크롤링 전 데이터 가용성 확인
- **파일 관리**: 공고별로 체계적인 폴더 구조로 첨부파일 정리

## 완전 초기 설정

### 1단계: 프로젝트 다운로드
```bash
# Git으로 클론하는 경우
git clone [repository-url]
cd bankruptcy-auction-crawling

# 또는 ZIP 파일을 다운로드한 경우
# 압축 해제 후 폴더로 이동
cd bankruptcy-auction-crawling
```

### 2단계: Python 가상환경 생성
```bash
# Python 가상환경 생성
python3 -m venv venv

# 가상환경 활성화 (macOS/Linux)
source venv/bin/activate

# 가상환경 활성화 (Windows)
# venv\Scripts\activate

# 성공하면 프롬프트 앞에 (venv) 표시됨
```

### 3단계: 의존성 설치
```bash
# 필수 라이브러리 설치
pip install -r requirements_simple.txt

# 또는 모든 라이브러리 설치 (pandas 포함, Python 3.12 이하 권장)
# pip install -r requirements.txt
```

### 4단계: Playwright 브라우저 설치
```bash
# 브라우저 설치 (약 300MB)
playwright install
```

### 5단계: 설치 검증
```bash
# 간단한 테스트 실행
python main.py --preview
```

## 새 터미널에서 실행하기

새로운 터미널을 열었을 때는 반드시 가상환경을 활성화해야 합니다:

```bash
# 1. 프로젝트 디렉토리로 이동
cd /path/to/bankruptcy-auction-crawling

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 프롬프트에 (venv) 표시 확인 후 실행
python main.py --with-attachments --max-pages 2
```

## 사용법

### 기본 사용법

**일반 크롤링 (목록 정보만):**
```bash
python main.py --no-attachments
```

**첨부파일 포함 크롤링 (권장):**
```bash
python main.py --with-attachments
```

**기본 크롤링 (설정에 따라 첨부파일 포함/제외):**
```bash
python main.py
```

**특정 페이지부터 시작:**
```bash
python main.py --with-attachments --start-page 5
```

**최대 페이지 수 제한:**
```bash
python main.py --with-attachments --max-pages 3
```

### 실행 예제

**1-2페이지만 첨부파일 포함 크롤링:**
```bash
python main.py --with-attachments --start-page 1 --max-pages 2
```

**특정 페이지들만 크롤링:**
```bash
python main.py --pages 1 2 5
```

**빠른 기본 크롤링 (첨부파일 제외):**
```bash
python main.py --no-attachments --max-pages 1
```

### 미리보기 모드

크롤링 전 데이터 확인:
```bash
python main.py --preview
```

### 특정 페이지 크롤링

```bash
python main.py --pages 1 5 10 15
```

### 브라우저 표시 모드

```bash
python main.py --headless false
```

## 설정

### 기본 설정
`config.py` 파일에서 다음 설정을 변경할 수 있습니다:

- `DELAY_BETWEEN_REQUESTS`: 요청 간 지연 시간 (기본: 2초)
- `PAGE_LOAD_TIMEOUT`: 페이지 로드 타임아웃 (기본: 30초)
- `MAX_RETRIES`: 최대 재시도 횟수 (기본: 3회)
- `OUTPUT_FORMAT`: 출력 형식 ("csv", "json", "both")
- `HEADLESS`: 브라우저 헤드리스 모드 (기본: True)
- `DOWNLOAD_ATTACHMENTS`: 첨부파일 다운로드 활성화 (기본: True)
- `DOWNLOADS_DIR`: 첨부파일 저장 디렉토리 (기본: "downloads")

### 중요한 명령어 참조

**매번 새 터미널에서 실행 시:**
```bash
cd /path/to/bankruptcy-auction-crawling
source venv/bin/activate
python main.py --with-attachments --max-pages 2
```

**가상환경 상태 확인:**
```bash
# 프롬프트에 (venv) 표시되어야 함
# Python 경로 확인
which python
```

## 출력 파일

### 데이터 파일
크롤링 결과는 `output/` 디렉토리에 저장됩니다:

- `bankruptcy_auctions_YYYYMMDD_HHMMSS.csv`: CSV 형식 데이터
- `bankruptcy_auctions_YYYYMMDD_HHMMSS.json`: JSON 형식 데이터  
- `bankruptcy_auctions_YYYYMMDD_HHMMSS_summary.txt`: 크롤링 요약 통계
- `attachment_summary_YYYYMMDD_HHMMSS.json`: 첨부파일 다운로드 요약

### 첨부파일 구조
첨부파일은 `downloads/` 디렉토리에 공고별로 정리됩니다:

```
downloads/
├── notice_405_파산재단_재고자산_일괄매각_공고/
│   ├── 01_2024하합101142_자산매각공고문.pdf
│   └── 02_기타_첨부파일.hwp
├── notice_404_환가포기_공고/
│   └── 01_환가포기_공고문.pdf
└── ...
```

## 프로젝트 구조

```
bankruptcy-auction-crawling/
├── config.py                 # 설정 파일
├── main.py                   # 메인 애플리케이션
├── requirements.txt          # 의존성 목록
├── crawler/                  # 크롤러 모듈
│   ├── __init__.py
│   ├── browser_controller.py       # 브라우저 제어
│   ├── data_extractor.py           # 기본 데이터 추출
│   ├── detail_extractor.py         # 상세 페이지 데이터 추출
│   ├── attachment_downloader.py    # 첨부파일 다운로더
│   ├── pagination_handler.py       # 기본 페이지네이션 처리
│   ├── enhanced_pagination_handler.py # 첨부파일 포함 페이지네이션
│   └── data_storage.py             # 데이터 저장
├── utils/                    # 유틸리티 모듈
│   ├── __init__.py
│   ├── logger.py             # 로깅 설정
│   └── error_handler.py      # 오류 처리
├── output/                   # 출력 파일 디렉토리
├── downloads/                # 첨부파일 다운로드 디렉토리
└── logs/                     # 로그 파일 디렉토리
```

## 로깅

모든 실행 과정은 `logs/` 디렉토리에 상세히 기록됩니다. 로그 레벨은 `config.py`에서 조정할 수 있습니다.

## 주의사항

- 웹사이트 서버에 부담을 주지 않도록 적절한 지연 시간을 설정하세요
- 첨부파일 다운로드 시 충분한 디스크 공간을 확보하세요 (공고당 평균 0.5-2MB)
- 대량 크롤링 시 네트워크 연결 상태를 확인하세요
- 사이트 구조 변경 시 데이터 추출 로직을 업데이트해야 할 수 있습니다
- 첨부파일 다운로드는 처리 시간이 더 오래 걸립니다 (공고당 약 3-5초 추가)

## 문제 해결

### 가장 일반적인 문제

#### 1. `ModuleNotFoundError: No module named 'playwright'`
**원인**: 가상환경이 활성화되지 않음
**해결책**:
```bash
# 프로젝트 디렉토리로 이동
cd /path/to/bankruptcy-auction-crawling

# 가상환경 활성화
source venv/bin/activate

# 프롬프트에 (venv) 표시 확인 후 재실행
python main.py --with-attachments --max-pages 2
```

#### 2. 가상환경 활성화 확인 방법
```bash
# 현재 Python 경로 확인 (가상환경이 활성화된 경우)
which python
# 결과: /path/to/project/venv/bin/python

# 설치된 패키지 확인
pip list | grep playwright
```

#### 3. 완전 재설치가 필요한 경우
```bash
# 기존 가상환경 삭제
rm -rf venv

# 새로 설정
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_simple.txt
playwright install
```

### 기타 문제들

1. **브라우저 실행 실패**: `playwright install` 명령어로 브라우저를 다시 설치하세요
2. **페이지 로드 실패**: 네트워크 연결을 확인하고 타임아웃 설정을 늘려보세요
3. **데이터 추출 실패**: 사이트 구조가 변경되었을 수 있습니다. 로그를 확인하세요
4. **첨부파일 다운로드 실패**: 디스크 공간 및 네트워크 연결을 확인하세요

### 로그 확인

상세한 오류 정보는 `logs/` 디렉토리의 로그 파일에서 확인할 수 있습니다.

## 라이센스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다. 상업적 사용 시 관련 법규를 확인하시기 바랍니다.