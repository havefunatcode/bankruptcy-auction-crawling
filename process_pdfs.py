#!/usr/bin/env python3
"""
PDF 일괄 처리 CLI (opendataloader-pdf 기반).

다운로드된 파산자 공매 PDF를 한 번의 JVM 호출로 변환하고,
JSON 출력을 디스크에 저장하거나 PostgreSQL에 영속화한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from pdf_processing import PDFPipeline, PipelineConfig
from pdf_processing.persistence import PDFDocumentRepository
from utils.logger import setup_logger


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="opendataloader-pdf 기반 PDF 일괄 추출 + DB 저장",
    )
    parser.add_argument("--downloads-dir", default=None, help="PDF 입력 루트")
    parser.add_argument("--output-dir", default=None, help="JSON 출력 디렉토리")
    parser.add_argument("--hybrid", default=None,
                        choices=[None, "docling-fast", "hancom-ai"],
                        help="하이브리드 AI 모드 활성화")
    parser.add_argument("--hybrid-url", default=None, help="원격 하이브리드 서버 URL")
    parser.add_argument("--hybrid-fallback", action="store_true",
                        help="하이브리드 실패 시 로컬 모드로 폴백")
    parser.add_argument("--store-db", action="store_true",
                        help="추출 결과를 PostgreSQL에 저장")
    parser.add_argument("--init-db", action="store_true",
                        help="DB 스키마 초기화 후 종료")
    parser.add_argument("--test-db", action="store_true",
                        help="DB 연결 테스트 후 종료")
    return parser


def _make_pipeline(args: argparse.Namespace) -> PDFPipeline:
    pipeline_config = PipelineConfig.from_module(config)
    if args.downloads_dir:
        pipeline_config.downloads_dir = args.downloads_dir
    if args.output_dir:
        pipeline_config.output_dir = args.output_dir
    if args.hybrid:
        pipeline_config.hybrid = args.hybrid
    if args.hybrid_url:
        pipeline_config.hybrid_url = args.hybrid_url
    if args.hybrid_fallback:
        pipeline_config.hybrid_fallback = True
    return PDFPipeline(pipeline_config)


def main() -> int:
    args = _build_argparser().parse_args()
    logger = setup_logger(__name__)

    if args.test_db or args.init_db or args.store_db:
        try:
            from database.database_manager import DatabaseManager
        except ImportError as e:
            print(f"❌ DB 모듈 로드 실패: {e}")
            return 1
        db = DatabaseManager()
        if args.test_db:
            ok = db.test_connection() if hasattr(db, "test_connection") else False
            print("✅ DB 연결 성공" if ok else "❌ DB 연결 실패")
            return 0 if ok else 1
        if args.init_db:
            ok = db.initialize_database()
            print("✅ DB 스키마 초기화 완료" if ok else "❌ DB 스키마 초기화 실패")
            return 0 if ok else 1
    else:
        db = None

    pipeline = _make_pipeline(args)
    if not Path(pipeline.config.downloads_dir).exists():
        print(f"❌ 다운로드 디렉토리가 없습니다: {pipeline.config.downloads_dir}")
        return 1

    print(f"▶ PDF 변환 시작 (downloads={pipeline.config.downloads_dir}, "
          f"hybrid={pipeline.config.hybrid or 'off'})")
    result = pipeline.run()

    total_docs = sum(len(v) for v in result.documents.values())
    print(f"✅ 변환 완료: {len(result.documents)} notice / {total_docs} PDF")
    if result.failed:
        print(f"⚠️ 실패 {len(result.failed)} 건")
        for nf in result.failed:
            print(f"   - notice_{nf.notice_id}: {nf.source_path.name}")

    if args.store_db:
        from database.database_manager import DatabaseManager
        db = DatabaseManager()
        if not db.initialize_database():
            print("❌ DB 초기화 실패 — 저장 중단")
            return 1
        repo = PDFDocumentRepository(db)
        stored = 0
        for notice_id, docs in result.documents.items():
            for doc in docs:
                doc.metadata.setdefault("notice_id", notice_id)
                outcome = repo.store(doc)
                if outcome.document_id is not None:
                    stored += 1
                    logger.info(
                        "stored notice=%s file=%s id=%s texts=%d tables=%d images=%d",
                        notice_id, doc.file_name, outcome.document_id,
                        outcome.text_inserted, outcome.tables_inserted,
                        outcome.images_inserted,
                    )
        print(f"💾 DB 저장 완료: {stored} 문서")

    return 0


if __name__ == "__main__":
    sys.exit(main())
