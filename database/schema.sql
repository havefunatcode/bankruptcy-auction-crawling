-- PostgreSQL schema for bankruptcy auction PDF processing
-- Database: bankruptcy_auction

-- Create database if it doesn't exist
-- CREATE DATABASE bankruptcy_auction;

-- Table for PDF document metadata
CREATE TABLE IF NOT EXISTS pdf_documents (
    id SERIAL PRIMARY KEY,
    notice_id VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_size BIGINT,
    page_count INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    CONSTRAINT unique_document UNIQUE(notice_id, file_name)
);

-- Table for extracted text content
CREATE TABLE IF NOT EXISTS pdf_text_content (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text_content TEXT,
    bbox_x0 FLOAT,
    bbox_y0 FLOAT,
    bbox_x1 FLOAT,
    bbox_y1 FLOAT,
    font_size FLOAT,
    font_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for extracted tables
CREATE TABLE IF NOT EXISTS pdf_tables (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    table_index INTEGER NOT NULL,
    table_data JSONB NOT NULL,
    row_count INTEGER,
    col_count INTEGER,
    bbox_x0 FLOAT,
    bbox_y0 FLOAT,
    bbox_x1 FLOAT,
    bbox_y1 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for extracted images
CREATE TABLE IF NOT EXISTS pdf_images (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    image_index INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    format VARCHAR(50),
    file_size BIGINT,
    bbox_x0 FLOAT,
    bbox_y0 FLOAT,
    bbox_x1 FLOAT,
    bbox_y1 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pdf_documents_notice_id ON pdf_documents(notice_id);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_processed_at ON pdf_documents(processed_at);
CREATE INDEX IF NOT EXISTS idx_pdf_text_document_page ON pdf_text_content(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_pdf_tables_document_page ON pdf_tables(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_pdf_images_document_page ON pdf_images(document_id, page_number);

-- Full-text search index for text content
CREATE INDEX IF NOT EXISTS idx_pdf_text_content_fts ON pdf_text_content USING gin(to_tsvector('korean', text_content));

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for updating updated_at on pdf_documents
CREATE TRIGGER update_pdf_documents_updated_at 
    BEFORE UPDATE ON pdf_documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE pdf_documents IS 'Metadata for processed PDF documents';
COMMENT ON TABLE pdf_text_content IS 'Extracted text content with positioning information';
COMMENT ON TABLE pdf_tables IS 'Structured table data extracted from PDFs';
COMMENT ON TABLE pdf_images IS 'Image metadata and file references extracted from PDFs';

COMMENT ON COLUMN pdf_text_content.bbox_x0 IS 'Left bounding box coordinate';
COMMENT ON COLUMN pdf_text_content.bbox_y0 IS 'Bottom bounding box coordinate';
COMMENT ON COLUMN pdf_text_content.bbox_x1 IS 'Right bounding box coordinate';
COMMENT ON COLUMN pdf_text_content.bbox_y1 IS 'Top bounding box coordinate';

COMMENT ON COLUMN pdf_tables.table_data IS 'JSON structure containing table rows and columns';

-- Views for common queries
CREATE OR REPLACE VIEW pdf_processing_summary AS
SELECT 
    pd.notice_id,
    pd.file_name,
    pd.page_count,
    pd.processed_at,
    COUNT(DISTINCT ptc.page_number) as pages_with_text,
    COUNT(pt.id) as total_tables,
    COUNT(pi.id) as total_images,
    pg_size_pretty(SUM(pd.file_size)) as total_file_size
FROM pdf_documents pd
LEFT JOIN pdf_text_content ptc ON pd.id = ptc.document_id
LEFT JOIN pdf_tables pt ON pd.id = pt.document_id
LEFT JOIN pdf_images pi ON pd.id = pi.document_id
GROUP BY pd.id, pd.notice_id, pd.file_name, pd.page_count, pd.processed_at
ORDER BY pd.processed_at DESC;