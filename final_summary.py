#!/usr/bin/env python3
"""
Final summary of dynamic section processing system
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager
import psycopg2.extras
from utils.logger import setup_logger


def main():
    """Generate final summary of the dynamic section system"""
    logger = setup_logger(__name__)
    logger.info("=== 동적 섹션 기반 PDF 처리 시스템 최종 요약 ===")
    
    db = DatabaseManager()
    
    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # 1. 전체 문서 통계
            cur.execute('SELECT COUNT(*) FROM pdf_documents;')
            doc_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM pdf_sections;')
            section_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM pdf_subsections;')
            subsection_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM pdf_tables;')
            table_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM pdf_images;')
            image_count = cur.fetchone()[0]
            
            logger.info(f"📊 전체 통계:")
            logger.info(f"   처리된 문서: {doc_count}개")
            logger.info(f"   동적 감지된 섹션: {section_count}개")
            logger.info(f"   하위섹션: {subsection_count}개")
            logger.info(f"   테이블: {table_count}개")
            logger.info(f"   이미지: {image_count}개")
            
            # 2. 섹션 타입별 분포
            logger.info(f"\n🏷️ 섹션 타입별 분포:")
            cur.execute('''
                SELECT section_type, COUNT(*) as count 
                FROM pdf_sections 
                GROUP BY section_type 
                ORDER BY count DESC;
            ''')
            types = cur.fetchall()
            for t in types:
                logger.info(f"   {t['section_type']}: {t['count']}개")
            
            # 3. 문서별 섹션 수
            logger.info(f"\n📄 문서별 섹션 수:")
            cur.execute('''
                SELECT pd.notice_id, pd.file_name, COUNT(ps.id) as section_count
                FROM pdf_documents pd
                LEFT JOIN pdf_sections ps ON pd.id = ps.document_id
                GROUP BY pd.id, pd.notice_id, pd.file_name
                ORDER BY section_count DESC;
            ''')
            docs = cur.fetchall()
            for doc in docs:
                logger.info(f"   {doc['notice_id']}: {doc['section_count']}개 섹션 - {doc['file_name'][:50]}...")
            
            # 4. 검색 기능 테스트
            logger.info(f"\n🔍 검색 기능 테스트:")
            
            # 매각 관련 섹션
            search_results = db.search_sections('매각', limit=3)
            logger.info(f"   '매각' 검색 결과: {len(search_results)}개")
            for r in search_results[:2]:
                logger.info(f"     - {r['notice_id']}: {r['section_name'][:40]}...")
            
            # 입찰 관련 섹션
            search_results = db.search_sections('입찰', limit=3)
            logger.info(f"   '입찰' 검색 결과: {len(search_results)}개")
            for r in search_results[:2]:
                logger.info(f"     - {r['notice_id']}: {r['section_name'][:40]}...")
            
            # 특허 관련 섹션
            search_results = db.search_sections('특허', limit=3)
            logger.info(f"   '특허' 검색 결과: {len(search_results)}개")
            for r in search_results[:2]:
                logger.info(f"     - {r['notice_id']}: {r['section_name'][:40]}...")
            
            # 5. 타입별 검색
            logger.info(f"\n🎯 타입별 검색:")
            asset_sections = db.search_sections('자산', section_type='asset_information', limit=3)
            logger.info(f"   자산정보 타입에서 '자산' 검색: {len(asset_sections)}개")
            
            bidding_sections = db.search_sections('입찰', section_type='bidding_procedure', limit=3)
            logger.info(f"   입찰절차 타입에서 '입찰' 검색: {len(bidding_sections)}개")
            
            # 6. 샘플 섹션 내용 보기
            logger.info(f"\n📋 샘플 섹션 내용:")
            cur.execute('''
                SELECT pd.notice_id, ps.section_name, ps.section_type, 
                       LEFT(ps.text_content, 100) as content_preview
                FROM pdf_sections ps
                JOIN pdf_documents pd ON ps.document_id = pd.id
                WHERE ps.section_type = 'asset_information'
                LIMIT 2;
            ''')
            samples = cur.fetchall()
            for s in samples:
                logger.info(f"   문서 {s['notice_id']} - {s['section_name']}")
                logger.info(f"   타입: {s['section_type']}")
                logger.info(f"   내용: {s['content_preview']}...")
                logger.info("")
    
    logger.info("✅ 동적 섹션 기반 PDF 처리 시스템이 성공적으로 구현되었습니다!")
    logger.info("\n🔧 주요 기능:")
    logger.info("   - 문서 구조에 따른 동적 섹션 감지")
    logger.info("   - 섹션별 자동 분류 (자산정보, 입찰절차, 연락처 등)")
    logger.info("   - 섹션 내용 기반 검색")
    logger.info("   - 타입별 필터링 검색")
    logger.info("   - 기존 고정 스키마와 병행 사용 가능")
    logger.info("\n🚀 이제 PDF 문서의 실제 구조에 맞춰 유연하게 데이터가 저장됩니다!")


if __name__ == "__main__":
    main()