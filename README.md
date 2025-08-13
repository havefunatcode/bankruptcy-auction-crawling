# Bankruptcy Auction Crawler

한국 대법원 파산자 공매 정보 크롤러입니다.

## 개요

이 프로젝트는 https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work 사이트에서 파산자 공매 정보를 자동으로 수집하는 Python 크롤러입니다.

## 주요 기능

- **자동 페이지 탐색**: 첫 페이지부터 마지막 페이지까지 자동으로 탐색
- **데이터 추출**: 파산자 공매 정보 (관할청, 사건번호, 제목, 조회수 등) 추출
- **다중 포맷 지원**: CSV, JSON 형식으로 데이터 저장
- **오류 처리**: 강력한 재시도 로직과 오류 복구 메커니즘
- **속도 제한**: 웹사이트에 부담을 주지 않는 적절한 속도 제한
- **미리보기 모드**: 실제 크롤링 전 데이터 가용성 확인

## 설치

1. 저장소 클론 또는 다운로드
2. 의존성 설치:
```bash
pip install -r requirements.txt
```

3. Playwright 브라우저 설치:
```bash
playwright install
```

## 사용법

### 기본 사용법

전체 크롤링:
```bash
python main.py
```

특정 페이지부터 시작:
```bash
python main.py --start-page 5
```

최대 페이지 수 제한:
```bash
python main.py --max-pages 10
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

`config.py` 파일에서 다음 설정을 변경할 수 있습니다:

- `DELAY_BETWEEN_REQUESTS`: 요청 간 지연 시간 (기본: 2초)
- `PAGE_LOAD_TIMEOUT`: 페이지 로드 타임아웃 (기본: 30초)
- `MAX_RETRIES`: 최대 재시도 횟수 (기본: 3회)
- `OUTPUT_FORMAT`: 출력 형식 ("csv", "json", "both")
- `HEADLESS`: 브라우저 헤드리스 모드 (기본: True)

## 출력 파일

크롤링 결과는 `output/` 디렉토리에 저장됩니다:

- `bankruptcy_auctions_YYYYMMDD_HHMMSS.csv`: CSV 형식 데이터
- `bankruptcy_auctions_YYYYMMDD_HHMMSS.json`: JSON 형식 데이터
- `bankruptcy_auctions_YYYYMMDD_HHMMSS_summary.txt`: 크롤링 요약 통계

## 프로젝트 구조

```
bankruptcy-auction-crawling/
├── config.py                 # 설정 파일
├── main.py                   # 메인 애플리케이션
├── requirements.txt          # 의존성 목록
├── crawler/                  # 크롤러 모듈
│   ├── __init__.py
│   ├── browser_controller.py # 브라우저 제어
│   ├── data_extractor.py     # 데이터 추출
│   ├── pagination_handler.py # 페이지네이션 처리
│   └── data_storage.py       # 데이터 저장
├── utils/                    # 유틸리티 모듈
│   ├── __init__.py
│   ├── logger.py             # 로깅 설정
│   └── error_handler.py      # 오류 처리
├── output/                   # 출력 파일 디렉토리
└── logs/                     # 로그 파일 디렉토리
```

## 로깅

모든 실행 과정은 `logs/` 디렉토리에 상세히 기록됩니다. 로그 레벨은 `config.py`에서 조정할 수 있습니다.

## 주의사항

- 웹사이트 서버에 부담을 주지 않도록 적절한 지연 시간을 설정하세요
- 대량의 데이터 크롤링 시 충분한 디스크 공간을 확보하세요
- 사이트 구조 변경 시 데이터 추출 로직을 업데이트해야 할 수 있습니다

## 문제 해결

### 일반적인 문제

1. **브라우저 실행 실패**: `playwright install` 명령어로 브라우저를 다시 설치하세요
2. **페이지 로드 실패**: 네트워크 연결을 확인하고 타임아웃 설정을 늘려보세요
3. **데이터 추출 실패**: 사이트 구조가 변경되었을 수 있습니다. 로그를 확인하세요

### 로그 확인

상세한 오류 정보는 `logs/` 디렉토리의 로그 파일에서 확인할 수 있습니다.

## 라이센스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다. 상업적 사용 시 관련 법규를 확인하시기 바랍니다.