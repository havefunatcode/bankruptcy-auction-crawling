-- MySQL 8.0+ schema for bankruptcy auction PDF processing
-- Character set: utf8mb4, collation: utf8mb4_unicode_ci

CREATE TABLE IF NOT EXISTS pdf_documents (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    notice_id       VARCHAR(255)    NOT NULL,
    file_path       TEXT            NOT NULL,
    file_name       VARCHAR(500)    NOT NULL,
    file_size       BIGINT,
    page_count      INT,
    processed_at    DATETIME        DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uniq_document (notice_id, file_name),
    KEY idx_pdf_documents_notice_id (notice_id),
    KEY idx_pdf_documents_processed_at (processed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Metadata for processed PDF documents';

CREATE TABLE IF NOT EXISTS pdf_text_content (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    document_id     INT             NOT NULL,
    page_number     INT             NOT NULL,
    text_content    TEXT,
    bbox_x0         DOUBLE,
    bbox_y0         DOUBLE,
    bbox_x1         DOUBLE,
    bbox_y1         DOUBLE,
    font_size       DOUBLE,
    font_name       VARCHAR(255),
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    KEY idx_pdf_text_document_page (document_id, page_number),
    -- 한글 전문 검색: ngram 파서 사용 (MySQL 8.0+)
    FULLTEXT KEY ft_pdf_text_content (text_content) WITH PARSER ngram,

    CONSTRAINT fk_pdf_text_document
        FOREIGN KEY (document_id) REFERENCES pdf_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Extracted text content with positioning';

CREATE TABLE IF NOT EXISTS pdf_tables (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    document_id     INT             NOT NULL,
    page_number     INT             NOT NULL,
    table_index     INT             NOT NULL,
    table_data      JSON            NOT NULL,
    row_count       INT,
    col_count       INT,
    bbox_x0         DOUBLE,
    bbox_y0         DOUBLE,
    bbox_x1         DOUBLE,
    bbox_y1         DOUBLE,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    KEY idx_pdf_tables_document_page (document_id, page_number),

    CONSTRAINT fk_pdf_tables_document
        FOREIGN KEY (document_id) REFERENCES pdf_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Structured table data extracted from PDFs';

CREATE TABLE IF NOT EXISTS pdf_images (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    document_id     INT             NOT NULL,
    page_number     INT             NOT NULL,
    image_index     INT             NOT NULL,
    image_path      TEXT            NOT NULL,
    width           INT,
    height          INT,
    format          VARCHAR(50),
    file_size       BIGINT,
    bbox_x0         DOUBLE,
    bbox_y0         DOUBLE,
    bbox_x1         DOUBLE,
    bbox_y1         DOUBLE,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,

    KEY idx_pdf_images_document_page (document_id, page_number),

    CONSTRAINT fk_pdf_images_document
        FOREIGN KEY (document_id) REFERENCES pdf_documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Image metadata and file references extracted from PDFs';

-- 처리 요약 뷰 (file_size는 바이트 합계로 반환)
CREATE OR REPLACE VIEW pdf_processing_summary AS
SELECT
    pd.notice_id,
    pd.file_name,
    pd.page_count,
    pd.processed_at,
    COUNT(DISTINCT ptc.page_number)                    AS pages_with_text,
    COUNT(DISTINCT pt.id)                              AS total_tables,
    COUNT(DISTINCT pi.id)                              AS total_images,
    COALESCE(SUM(pd.file_size), 0)                     AS total_file_size_bytes
FROM pdf_documents pd
LEFT JOIN pdf_text_content ptc ON pd.id = ptc.document_id
LEFT JOIN pdf_tables pt        ON pd.id = pt.document_id
LEFT JOIN pdf_images pi        ON pd.id = pi.document_id
GROUP BY pd.id, pd.notice_id, pd.file_name, pd.page_count, pd.processed_at
ORDER BY pd.processed_at DESC;
