-- Extension to existing schema for dynamic section-based PDF processing
-- This script adds new tables and columns to support dynamic section extraction

-- Keep existing structured content for backward compatibility
ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS structured_content JSONB;
ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS extraction_error TEXT;

-- Add new columns for dynamic section processing
ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS 
    dynamic_sections JSONB DEFAULT NULL;

ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS 
    section_extraction_status VARCHAR(50) DEFAULT 'pending';

ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS 
    section_extraction_error TEXT DEFAULT NULL;

ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS 
    document_metadata JSONB DEFAULT NULL;

-- Create dedicated table for section content
CREATE TABLE IF NOT EXISTS pdf_sections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    section_key VARCHAR(255) NOT NULL,
    section_name VARCHAR(500) NOT NULL,
    section_type VARCHAR(100),
    section_number VARCHAR(50),
    original_title TEXT,
    text_content TEXT,
    start_line INTEGER,
    content_length INTEGER,
    line_count INTEGER,
    section_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique sections per document
    CONSTRAINT unique_document_section UNIQUE(document_id, section_key)
);

-- Create table for subsections
CREATE TABLE IF NOT EXISTS pdf_subsections (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES pdf_sections(id) ON DELETE CASCADE,
    subsection_key VARCHAR(255) NOT NULL,
    subsection_name VARCHAR(500) NOT NULL,
    text_content TEXT,
    subsection_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique subsections per section
    CONSTRAINT unique_section_subsection UNIQUE(section_id, subsection_key)
);

-- Create table for section-table relationships
CREATE TABLE IF NOT EXISTS pdf_section_tables (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES pdf_sections(id) ON DELETE CASCADE,
    table_id INTEGER NOT NULL REFERENCES pdf_tables(id) ON DELETE CASCADE,
    assignment_confidence FLOAT DEFAULT 1.0,
    assignment_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique relationships
    CONSTRAINT unique_section_table UNIQUE(section_id, table_id)
);

-- Create table for section-image relationships
CREATE TABLE IF NOT EXISTS pdf_section_images (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES pdf_sections(id) ON DELETE CASCADE,
    image_id INTEGER NOT NULL REFERENCES pdf_images(id) ON DELETE CASCADE,
    assignment_confidence FLOAT DEFAULT 1.0,
    assignment_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique relationships
    CONSTRAINT unique_section_image UNIQUE(section_id, image_id)
);

-- Create table for document processing results
CREATE TABLE IF NOT EXISTS pdf_processing_results (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    processing_method VARCHAR(50) NOT NULL, -- 'structured' or 'dynamic_sections'
    success BOOLEAN NOT NULL,
    confidence_score FLOAT,
    processing_notes TEXT[],
    error_message TEXT,
    result_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Allow multiple processing results per document for different methods
    CONSTRAINT unique_document_method UNIQUE(document_id, processing_method)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_pdf_documents_structured_content ON pdf_documents USING gin(structured_content);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_extraction_status ON pdf_documents(extraction_status);
CREATE INDEX IF NOT EXISTS idx_pdf_sections_document_id ON pdf_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_pdf_sections_type ON pdf_sections(section_type);
CREATE INDEX IF NOT EXISTS idx_pdf_subsections_section_id ON pdf_subsections(section_id);
CREATE INDEX IF NOT EXISTS idx_pdf_section_tables_section_id ON pdf_section_tables(section_id);
CREATE INDEX IF NOT EXISTS idx_pdf_section_images_section_id ON pdf_section_images(section_id);
CREATE INDEX IF NOT EXISTS idx_pdf_processing_results_document_id ON pdf_processing_results(document_id);

-- Full-text search indexes for section content
CREATE INDEX IF NOT EXISTS idx_pdf_sections_text_fts 
    ON pdf_sections USING gin(to_tsvector('simple', text_content));

CREATE INDEX IF NOT EXISTS idx_pdf_subsections_text_fts 
    ON pdf_subsections USING gin(to_tsvector('simple', text_content));

-- JSONB indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_pdf_sections_metadata ON pdf_sections USING gin(section_metadata);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_dynamic_sections ON pdf_documents USING gin(dynamic_sections);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_metadata ON pdf_documents USING gin(document_metadata);
CREATE INDEX IF NOT EXISTS idx_pdf_processing_results_data ON pdf_processing_results USING gin(result_data);

-- Update the processing summary view to include section information
DROP VIEW IF EXISTS pdf_processing_summary;
CREATE OR REPLACE VIEW pdf_processing_summary AS
SELECT 
    pd.notice_id,
    pd.file_name,
    pd.page_count,
    pd.processed_at,
    pd.extraction_status,
    pd.section_extraction_status,
    COUNT(DISTINCT ptc.page_number) as pages_with_text,
    COUNT(pt.id) as total_tables,
    COUNT(pi.id) as total_images,
    COUNT(ps.id) as total_sections,
    COUNT(pss.id) as total_subsections,
    pg_size_pretty(SUM(pd.file_size)) as total_file_size,
    CASE 
        WHEN pd.dynamic_sections IS NOT NULL THEN 'dynamic_sections'
        WHEN pd.structured_content IS NOT NULL THEN 'structured'
        ELSE 'raw_only'
    END as processing_type
FROM pdf_documents pd
LEFT JOIN pdf_text_content ptc ON pd.id = ptc.document_id
LEFT JOIN pdf_tables pt ON pd.id = pt.document_id
LEFT JOIN pdf_images pi ON pd.id = pi.document_id
LEFT JOIN pdf_sections ps ON pd.id = ps.document_id
LEFT JOIN pdf_subsections pss ON ps.id = pss.section_id
GROUP BY pd.id, pd.notice_id, pd.file_name, pd.page_count, pd.processed_at, 
         pd.extraction_status, pd.section_extraction_status, pd.dynamic_sections, pd.structured_content
ORDER BY pd.processed_at DESC;

-- Create view for section analysis
CREATE OR REPLACE VIEW pdf_section_analysis AS
SELECT 
    pd.notice_id,
    pd.file_name,
    ps.section_key,
    ps.section_name,
    ps.section_type,
    ps.content_length,
    ps.line_count,
    COUNT(pst.table_id) as tables_count,
    COUNT(psi.image_id) as images_count,
    COUNT(pss.id) as subsections_count,
    ps.section_metadata
FROM pdf_documents pd
JOIN pdf_sections ps ON pd.id = ps.document_id
LEFT JOIN pdf_section_tables pst ON ps.id = pst.section_id
LEFT JOIN pdf_section_images psi ON ps.id = psi.section_id
LEFT JOIN pdf_subsections pss ON ps.id = pss.section_id
GROUP BY pd.notice_id, pd.file_name, ps.id, ps.section_key, ps.section_name, 
         ps.section_type, ps.content_length, ps.line_count, ps.section_metadata
ORDER BY pd.notice_id, ps.section_key;

-- Create view for content search across sections
CREATE OR REPLACE VIEW pdf_section_search AS
SELECT 
    pd.notice_id,
    pd.file_name,
    ps.section_key,
    ps.section_name,
    ps.section_type,
    ps.text_content,
    ps.section_metadata,
    'section' as content_type
FROM pdf_documents pd
JOIN pdf_sections ps ON pd.id = ps.document_id
WHERE ps.text_content IS NOT NULL AND LENGTH(ps.text_content) > 0

UNION ALL

SELECT 
    pd.notice_id,
    pd.file_name,
    ps.section_key || '/' || pss.subsection_key as section_key,
    pss.subsection_name as section_name,
    'subsection' as section_type,
    pss.text_content,
    pss.subsection_metadata as section_metadata,
    'subsection' as content_type
FROM pdf_documents pd
JOIN pdf_sections ps ON pd.id = ps.document_id
JOIN pdf_subsections pss ON ps.id = pss.section_id
WHERE pss.text_content IS NOT NULL AND LENGTH(pss.text_content) > 0;

-- Keep original view for backward compatibility
CREATE OR REPLACE VIEW pdf_structured_analysis AS
SELECT 
    pd.id,
    pd.notice_id,
    pd.file_name,
    pd.extraction_status,
    pd.structured_content->>'schema_version' as schema_version,
    pd.structured_content->'document_meta'->>'title' as document_title,
    pd.structured_content->'sections'->'매각대상자산'->>'asset_type' as asset_type,
    jsonb_array_length(COALESCE(pd.structured_content->'sections'->'매각대상자산'->'assets', '[]'::jsonb)) as asset_count,
    pd.structured_content->'sections'->'입찰방법_최저입찰가'->>'bidding_type' as bidding_type,
    jsonb_array_length(COALESCE(pd.structured_content->'sections'->'입찰방법_최저입찰가'->'rounds', '[]'::jsonb)) as bid_rounds,
    pd.structured_content->'sections'->'기타사항_문의'->'trustee_contact'->>'organization' as trustee_org,
    jsonb_array_length(COALESCE(pd.structured_content->'quality'->'missing_sections', '[]'::jsonb)) as missing_sections_count,
    pd.processed_at,
    pd.created_at
FROM pdf_documents pd
WHERE pd.structured_content IS NOT NULL
ORDER BY pd.processed_at DESC;

-- Add comments for documentation
COMMENT ON TABLE pdf_sections IS 'Dynamically detected sections from PDF documents';
COMMENT ON TABLE pdf_subsections IS 'Subsections within main sections';
COMMENT ON TABLE pdf_section_tables IS 'Many-to-many relationship between sections and tables';
COMMENT ON TABLE pdf_section_images IS 'Many-to-many relationship between sections and images';
COMMENT ON TABLE pdf_processing_results IS 'Results from different processing methods';

COMMENT ON COLUMN pdf_documents.structured_content IS 'Structured JSON content extracted from PDF using AI parsing (legacy)';
COMMENT ON COLUMN pdf_documents.extraction_status IS 'Status of structured extraction: pending, processing, completed, failed (legacy)';
COMMENT ON COLUMN pdf_documents.extraction_error IS 'Error message if extraction failed (legacy)';
COMMENT ON COLUMN pdf_documents.dynamic_sections IS 'JSON structure containing dynamically detected sections';
COMMENT ON COLUMN pdf_documents.section_extraction_status IS 'Status of dynamic section extraction';
COMMENT ON COLUMN pdf_documents.document_metadata IS 'Document-level metadata extracted during processing';

COMMENT ON COLUMN pdf_sections.section_key IS 'Unique key for the section within the document';
COMMENT ON COLUMN pdf_sections.section_type IS 'Automatically classified section type';
COMMENT ON COLUMN pdf_sections.section_metadata IS 'JSON metadata about section content and analysis';

-- Create functions for common queries
CREATE OR REPLACE FUNCTION get_sections_by_type(doc_type VARCHAR)
RETURNS TABLE(
    notice_id VARCHAR,
    file_name VARCHAR,
    section_name VARCHAR,
    content_length INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pd.notice_id,
        pd.file_name,
        ps.section_name,
        ps.content_length
    FROM pdf_documents pd
    JOIN pdf_sections ps ON pd.id = ps.document_id
    WHERE ps.section_type = doc_type
    ORDER BY pd.notice_id, ps.section_key;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION search_section_content(search_term TEXT)
RETURNS TABLE(
    notice_id VARCHAR,
    file_name VARCHAR,
    section_name VARCHAR,
    content_type VARCHAR,
    relevance FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pss.notice_id,
        pss.file_name,
        pss.section_name,
        pss.content_type,
        ts_rank(to_tsvector('simple', pss.text_content), plainto_tsquery('simple', search_term)) as relevance
    FROM pdf_section_search pss
    WHERE to_tsvector('simple', pss.text_content) @@ plainto_tsquery('simple', search_term)
    ORDER BY relevance DESC;
END;
$$ LANGUAGE plpgsql;