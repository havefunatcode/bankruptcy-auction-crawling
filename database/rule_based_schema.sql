-- Rule-based PDF Section Processing Schema
-- Optimized for evidence tracking and confidence scoring

-- Drop existing tables if they exist
DROP TABLE IF EXISTS auction_patents CASCADE;
DROP TABLE IF EXISTS auction_items CASCADE;
DROP TABLE IF EXISTS auction_sections CASCADE;
DROP TABLE IF EXISTS auction_docs CASCADE;

-- Main document metadata table
CREATE TABLE auction_docs (
    id SERIAL PRIMARY KEY,
    notice_id VARCHAR(100) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    page_count INTEGER,
    
    -- PDF type and processing metadata
    pdf_type VARCHAR(20) NOT NULL DEFAULT 'unknown', -- 'digital', 'scanned'
    pdf_type_confidence REAL DEFAULT 0.0,
    processing_method VARCHAR(20) NOT NULL DEFAULT 'ocr', -- 'digital', 'ocr'
    
    -- Document summary
    title TEXT,
    document_type VARCHAR(50), -- 'asset_sale_notice', 'contract', etc.
    language VARCHAR(10) DEFAULT 'korean',
    
    -- Processing metadata
    total_sections INTEGER DEFAULT 0,
    total_blocks INTEGER DEFAULT 0,
    processing_confidence REAL DEFAULT 0.0,
    extraction_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    extraction_error TEXT,
    
    -- Quality metrics
    unknown_sections_count INTEGER DEFAULT 0,
    low_confidence_sections_count INTEGER DEFAULT 0,
    validation_errors JSONB DEFAULT '[]',
    
    -- Timestamps
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT unique_notice_file UNIQUE(notice_id, file_name),
    CONSTRAINT valid_pdf_type CHECK (pdf_type IN ('digital', 'scanned', 'unknown')),
    CONSTRAINT valid_processing_method CHECK (processing_method IN ('digital', 'ocr')),
    CONSTRAINT valid_status CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Section storage with JSONB content
CREATE TABLE auction_sections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES auction_docs(id) ON DELETE CASCADE,
    
    -- Section identification
    section_order INTEGER NOT NULL, -- Order within document
    section_id VARCHAR(200) NOT NULL, -- Unique section identifier
    
    -- Header information
    header_text TEXT NOT NULL,
    header_bbox JSONB, -- {page, x0, y0, x1, y1}
    
    -- Classification
    section_label VARCHAR(50) NOT NULL, -- ASSET_OVERVIEW, BID_SCHEDULE, etc.
    section_type VARCHAR(50) NOT NULL, -- asset, bidding, qualification, etc.
    content_type VARCHAR(20) NOT NULL, -- TABLE, LIST, PARAGRAPH, MIXED
    
    -- Raw content
    raw_content TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '{}', -- {raw, normalized, table?, evidence}
    
    -- Quality and evidence
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence JSONB NOT NULL DEFAULT '{}', -- Processing evidence and metadata
    validation_status VARCHAR(20) DEFAULT 'valid', -- 'valid', 'invalid', 'warning'
    validation_errors JSONB DEFAULT '[]',
    
    -- Processing metadata
    block_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    merge_history JSONB DEFAULT '[]',
    cross_page_continuation BOOLEAN DEFAULT FALSE,
    
    -- Content analysis
    has_dates BOOLEAN DEFAULT FALSE,
    has_money BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_tables BOOLEAN DEFAULT FALSE,
    has_registration_numbers BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT unique_section_per_doc UNIQUE(document_id, section_id),
    CONSTRAINT valid_section_label CHECK (section_label IN (
        'ASSET_OVERVIEW', 'BID_SCHEDULE', 'BID_METHOD', 'QUALIFICATION', 
        'CONTRACT', 'PAYMENT', 'CAUTIONS', 'CONTACT', 'APPENDIX', 'UNKNOWN'
    )),
    CONSTRAINT valid_content_type CHECK (content_type IN ('TABLE', 'LIST', 'PARAGRAPH', 'MIXED', 'EMPTY')),
    CONSTRAINT valid_validation_status CHECK (validation_status IN ('valid', 'invalid', 'warning'))
);

-- Optional: Structured patent information table
CREATE TABLE auction_patents (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES auction_docs(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES auction_sections(id) ON DELETE CASCADE,
    
    -- Patent identification
    patent_number VARCHAR(100),
    patent_type VARCHAR(50), -- 'patent', 'utility_model', 'design'
    registration_number VARCHAR(100),
    application_number VARCHAR(100),
    
    -- Patent details
    title TEXT,
    inventor TEXT,
    assignee TEXT,
    filing_date DATE,
    registration_date DATE,
    expiry_date DATE,
    
    -- Classification
    ipc_class VARCHAR(20), -- International Patent Classification
    korea_class VARCHAR(20),
    
    -- Asset information
    estimated_value BIGINT, -- in won
    minimum_bid BIGINT, -- in won
    bid_deposit BIGINT, -- in won
    
    -- Evidence and confidence
    extraction_confidence REAL DEFAULT 0.0,
    evidence JSONB DEFAULT '{}',
    validation_errors JSONB DEFAULT '[]',
    
    -- Source location
    source_page INTEGER,
    source_bbox JSONB,
    
    CONSTRAINT valid_patent_type CHECK (patent_type IN ('patent', 'utility_model', 'design', 'trademark'))
);

-- Optional: Other asset items table
CREATE TABLE auction_items (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES auction_docs(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES auction_sections(id) ON DELETE CASCADE,
    
    -- Item identification
    item_type VARCHAR(50), -- 'real_estate', 'equipment', 'vehicle', 'other'
    item_name TEXT,
    item_description TEXT,
    
    -- Location and specifications
    location TEXT,
    area DECIMAL(15,2), -- in square meters
    structure_type VARCHAR(100),
    use_purpose VARCHAR(100),
    
    -- Financial information
    estimated_value BIGINT, -- in won
    minimum_bid BIGINT, -- in won
    bid_deposit BIGINT, -- in won
    
    -- Legal information
    registration_info TEXT,
    restrictions TEXT,
    liens TEXT,
    
    -- Evidence and confidence
    extraction_confidence REAL DEFAULT 0.0,
    evidence JSONB DEFAULT '{}',
    validation_errors JSONB DEFAULT '[]',
    
    -- Source location
    source_page INTEGER,
    source_bbox JSONB,
    
    CONSTRAINT valid_item_type CHECK (item_type IN ('real_estate', 'equipment', 'vehicle', 'intellectual_property', 'other'))
);

-- Indexes for performance
CREATE INDEX idx_auction_docs_notice_id ON auction_docs(notice_id);
CREATE INDEX idx_auction_docs_status ON auction_docs(extraction_status);
CREATE INDEX idx_auction_docs_processed_at ON auction_docs(processed_at);

CREATE INDEX idx_auction_sections_document_id ON auction_sections(document_id);
CREATE INDEX idx_auction_sections_label ON auction_sections(section_label);
CREATE INDEX idx_auction_sections_type ON auction_sections(section_type);
CREATE INDEX idx_auction_sections_content_type ON auction_sections(content_type);
CREATE INDEX idx_auction_sections_order ON auction_sections(document_id, section_order);

-- GIN indexes for JSONB columns
CREATE INDEX idx_auction_sections_content_gin ON auction_sections USING GIN (content);
CREATE INDEX idx_auction_sections_evidence_gin ON auction_sections USING GIN (evidence);
CREATE INDEX idx_auction_docs_validation_errors_gin ON auction_docs USING GIN (validation_errors);

-- Full-text search indexes
CREATE INDEX idx_auction_sections_header_text ON auction_sections USING GIN (to_tsvector('simple', header_text));
CREATE INDEX idx_auction_sections_raw_content ON auction_sections USING GIN (to_tsvector('simple', raw_content));

-- Views for analysis and reporting

-- Document processing summary view
CREATE OR REPLACE VIEW auction_processing_summary AS
SELECT 
    d.id,
    d.notice_id,
    d.file_name,
    d.pdf_type,
    d.processing_method,
    d.total_sections,
    d.processing_confidence,
    d.extraction_status,
    d.unknown_sections_count,
    d.low_confidence_sections_count,
    CASE 
        WHEN d.unknown_sections_count > d.total_sections * 0.5 THEN 'poor'
        WHEN d.unknown_sections_count > d.total_sections * 0.2 THEN 'fair'
        ELSE 'good'
    END as quality_assessment,
    COUNT(s.id) as actual_sections,
    AVG(s.confidence) as avg_section_confidence,
    d.processed_at
FROM auction_docs d
LEFT JOIN auction_sections s ON d.id = s.document_id
GROUP BY d.id;

-- Section analysis view
CREATE OR REPLACE VIEW auction_section_analysis AS
SELECT 
    s.id,
    s.document_id,
    d.notice_id,
    s.section_label,
    s.section_type,
    s.content_type,
    s.confidence,
    s.validation_status,
    s.character_count,
    s.block_count,
    s.has_dates,
    s.has_money,
    s.has_phone,
    s.has_tables,
    s.has_registration_numbers,
    s.cross_page_continuation,
    CASE 
        WHEN s.confidence < 0.3 THEN 'low'
        WHEN s.confidence < 0.7 THEN 'medium'
        ELSE 'high'
    END as confidence_level
FROM auction_sections s
JOIN auction_docs d ON s.document_id = d.id;

-- Search functions

-- Function to search sections by content
CREATE OR REPLACE FUNCTION search_section_content(search_term TEXT, result_limit INTEGER DEFAULT 50)
RETURNS TABLE (
    document_id INTEGER,
    notice_id VARCHAR,
    section_label VARCHAR,
    section_type VARCHAR,
    header_text TEXT,
    content_snippet TEXT,
    confidence REAL,
    relevance REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.document_id,
        d.notice_id,
        s.section_label,
        s.section_type,
        s.header_text,
        LEFT(s.raw_content, 200) as content_snippet,
        s.confidence,
        ts_rank(to_tsvector('simple', s.raw_content), plainto_tsquery('simple', search_term)) as relevance
    FROM auction_sections s
    JOIN auction_docs d ON s.document_id = d.id
    WHERE to_tsvector('simple', s.raw_content) @@ plainto_tsquery('simple', search_term)
    ORDER BY relevance DESC, s.confidence DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get sections by type
CREATE OR REPLACE FUNCTION get_sections_by_type(section_type_param VARCHAR, result_limit INTEGER DEFAULT 100)
RETURNS TABLE (
    document_id INTEGER,
    notice_id VARCHAR,
    section_label VARCHAR,
    header_text TEXT,
    confidence FLOAT,
    character_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.document_id,
        d.notice_id,
        s.section_label,
        s.header_text,
        s.confidence,
        s.character_count
    FROM auction_sections s
    JOIN auction_docs d ON s.document_id = d.id
    WHERE s.section_type = section_type_param
    ORDER BY s.confidence DESC, d.processed_at DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update document statistics
CREATE OR REPLACE FUNCTION update_document_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE auction_docs SET
            total_sections = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = NEW.document_id
            ),
            unknown_sections_count = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = NEW.document_id 
                AND section_label = 'UNKNOWN'
            ),
            low_confidence_sections_count = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = NEW.document_id 
                AND confidence < 0.5
            ),
            processing_confidence = (
                SELECT COALESCE(AVG(confidence), 0.0)
                FROM auction_sections 
                WHERE document_id = NEW.document_id
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.document_id;
        
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE auction_docs SET
            total_sections = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = OLD.document_id
            ),
            unknown_sections_count = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = OLD.document_id 
                AND section_label = 'UNKNOWN'
            ),
            low_confidence_sections_count = (
                SELECT COUNT(*) 
                FROM auction_sections 
                WHERE document_id = OLD.document_id 
                AND confidence < 0.5
            ),
            processing_confidence = (
                SELECT COALESCE(AVG(confidence), 0.0)
                FROM auction_sections 
                WHERE document_id = OLD.document_id
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.document_id;
        
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER trigger_update_document_stats
    AFTER INSERT OR UPDATE OR DELETE ON auction_sections
    FOR EACH ROW EXECUTE FUNCTION update_document_stats();

-- Create trigger to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auction_docs_updated_at
    BEFORE UPDATE ON auction_docs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_auction_sections_updated_at
    BEFORE UPDATE ON auction_sections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Quality assessment functions

-- Function to identify review queue items
CREATE OR REPLACE FUNCTION get_review_queue(confidence_threshold FLOAT DEFAULT 0.5)
RETURNS TABLE (
    document_id INTEGER,
    notice_id VARCHAR,
    section_id INTEGER,
    section_label VARCHAR,
    confidence FLOAT,
    validation_status VARCHAR,
    issues TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.document_id,
        d.notice_id,
        s.id as section_id,
        s.section_label,
        s.confidence,
        s.validation_status,
        ARRAY[
            CASE WHEN s.section_label = 'UNKNOWN' THEN 'unknown_label' END,
            CASE WHEN s.confidence < confidence_threshold THEN 'low_confidence' END,
            CASE WHEN s.validation_status != 'valid' THEN 'validation_failed' END
        ]::TEXT[] as issues
    FROM auction_sections s
    JOIN auction_docs d ON s.document_id = d.id
    WHERE s.section_label = 'UNKNOWN' 
       OR s.confidence < confidence_threshold 
       OR s.validation_status != 'valid'
    ORDER BY s.confidence ASC, d.processed_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE auction_docs IS 'Main document metadata with PDF type detection and processing summary';
COMMENT ON TABLE auction_sections IS 'Section-based content storage with JSONB flexibility and evidence tracking';
COMMENT ON TABLE auction_patents IS 'Structured patent information extracted from sections';
COMMENT ON TABLE auction_items IS 'Other asset items extracted from sections';

COMMENT ON COLUMN auction_sections.content IS 'JSONB content: {raw, normalized, table?, evidence}';
COMMENT ON COLUMN auction_sections.evidence IS 'Processing evidence: {page, bbox, lineRange, method, confidence}';
COMMENT ON COLUMN auction_sections.section_label IS 'Standardized section labels from mapping dictionary';

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO auction_processor;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO auction_processor;