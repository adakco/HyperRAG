-- HyperRAG Database Schema
-- Multi-tenant, multi-language document management system

-- Create databases
CREATE DATABASE langfuse;

-- Switch to main database
\c hyperrag;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Documents table (main document metadata)
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    project TEXT NOT NULL,
    lang TEXT DEFAULT 'en' CHECK (lang IN ('en', 'fa')),
    latest_version TEXT,
    title TEXT,
    content_type TEXT,
    file_size BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document versions table
CREATE TABLE document_versions (
    doc_id TEXT NOT NULL,
    version TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    uri_raw TEXT NOT NULL,
    uri_clean TEXT,
    uri_processed TEXT,
    lang TEXT DEFAULT 'en' CHECK (lang IN ('en', 'fa')),
    chunk_count INTEGER DEFAULT 0,
    embedding_count INTEGER DEFAULT 0,
    processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (doc_id, version),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Document chunks table
CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id TEXT NOT NULL,
    version TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    lang TEXT DEFAULT 'en' CHECK (lang IN ('en', 'fa')),
    token_count INTEGER,
    embedding_id TEXT, -- Reference to Qdrant point ID
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (doc_id, version) REFERENCES document_versions(doc_id, version) ON DELETE CASCADE
);

-- Processing events table (CloudEvents)
CREATE TABLE processing_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    specversion TEXT NOT NULL DEFAULT '1.0',
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    datacontenttype TEXT DEFAULT 'application/json',
    data JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent sessions table
CREATE TABLE agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT,
    query TEXT NOT NULL,
    lang TEXT DEFAULT 'en' CHECK (lang IN ('en', 'fa')),
    token_budget INTEGER DEFAULT 4000,
    max_steps INTEGER DEFAULT 10,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed', 'timeout')),
    final_response TEXT,
    total_cost DECIMAL(10,6) DEFAULT 0,
    citations JSONB DEFAULT '[]',
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Agent steps table (for tracing)
CREATE TABLE agent_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,
    step_number INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    input_data JSONB NOT NULL,
    output_data JSONB,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message TEXT,
    cost DECIMAL(10,6) DEFAULT 0,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id) ON DELETE CASCADE
);

-- Evaluation results table
CREATE TABLE evaluation_results (
    eval_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID,
    doc_id TEXT,
    version TEXT,
    lang TEXT NOT NULL CHECK (lang IN ('en', 'fa')),
    metric_name TEXT NOT NULL,
    metric_value DECIMAL(5,4) NOT NULL,
    threshold DECIMAL(5,4),
    passed BOOLEAN GENERATED ALWAYS AS (metric_value >= threshold) STORED,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY (doc_id, version) REFERENCES document_versions(doc_id, version) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX idx_documents_tenant_project ON documents(tenant, project);
CREATE INDEX idx_documents_lang ON documents(lang);
CREATE INDEX idx_document_versions_status ON document_versions(processing_status);
CREATE INDEX idx_document_chunks_doc_version ON document_chunks(doc_id, version);
CREATE INDEX idx_document_chunks_lang ON document_chunks(lang);
CREATE INDEX idx_processing_events_type ON processing_events(type);
CREATE INDEX idx_processing_events_processed ON processing_events(processed);
CREATE INDEX idx_agent_sessions_tenant ON agent_sessions(tenant);
CREATE INDEX idx_agent_sessions_status ON agent_sessions(status);
CREATE INDEX idx_agent_steps_session ON agent_steps(session_id);
CREATE INDEX idx_evaluation_results_lang ON evaluation_results(lang);
CREATE INDEX idx_evaluation_results_metric ON evaluation_results(metric_name);

-- Full-text search indexes
CREATE INDEX idx_documents_title_gin ON documents USING gin(to_tsvector('english', title));
CREATE INDEX idx_document_chunks_content_gin ON document_chunks USING gin(to_tsvector('english', content));

-- Row Level Security (RLS) setup
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_results ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY tenant_isolation_documents ON documents
    USING (tenant = current_setting('app.tenant', true));

CREATE POLICY tenant_isolation_document_versions ON document_versions
    USING (doc_id IN (SELECT doc_id FROM documents WHERE tenant = current_setting('app.tenant', true)));

CREATE POLICY tenant_isolation_document_chunks ON document_chunks
    USING (doc_id IN (SELECT doc_id FROM documents WHERE tenant = current_setting('app.tenant', true)));

CREATE POLICY tenant_isolation_agent_sessions ON agent_sessions
    USING (tenant = current_setting('app.tenant', true));

CREATE POLICY tenant_isolation_agent_steps ON agent_steps
    USING (session_id IN (SELECT session_id FROM agent_sessions WHERE tenant = current_setting('app.tenant', true)));

CREATE POLICY tenant_isolation_evaluation_results ON evaluation_results
    USING (session_id IN (SELECT session_id FROM agent_sessions WHERE tenant = current_setting('app.tenant', true)));

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to get document statistics
CREATE OR REPLACE FUNCTION get_document_stats(p_tenant TEXT, p_lang TEXT DEFAULT NULL)
RETURNS TABLE (
    total_docs BIGINT,
    total_versions BIGINT,
    total_chunks BIGINT,
    completed_processing BIGINT,
    failed_processing BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT d.doc_id) as total_docs,
        COUNT(DISTINCT dv.version) as total_versions,
        COUNT(DISTINCT dc.chunk_id) as total_chunks,
        COUNT(DISTINCT CASE WHEN dv.processing_status = 'completed' THEN dv.version END) as completed_processing,
        COUNT(DISTINCT CASE WHEN dv.processing_status = 'failed' THEN dv.version END) as failed_processing
    FROM documents d
    LEFT JOIN document_versions dv ON d.doc_id = dv.doc_id
    LEFT JOIN document_chunks dc ON d.doc_id = dc.doc_id AND dv.version = dc.version
    WHERE d.tenant = p_tenant
    AND (p_lang IS NULL OR d.lang = p_lang);
END;
$$ LANGUAGE plpgsql;

-- Insert sample data for testing
INSERT INTO documents (doc_id, tenant, project, lang, title, content_type) VALUES
('sample-doc-1', 'acme', 'alpha', 'en', 'Sample English Document', 'text/plain'),
('sample-doc-2', 'acme', 'alpha', 'fa', 'سند نمونه فارسی', 'text/plain');

INSERT INTO document_versions (doc_id, version, sha256, uri_raw, lang, processing_status) VALUES
('sample-doc-1', 'v1', 'abc123', 's3://raw/acme/sample-doc-1.txt', 'en', 'completed'),
('sample-doc-2', 'v1', 'def456', 's3://raw/acme/sample-doc-2.txt', 'fa', 'completed');
