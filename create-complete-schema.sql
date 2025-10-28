-- Complete HyperRAG Database Schema
-- This script creates all necessary tables and indexes

-- Drop all existing tables (CAREFUL!)
DROP TABLE IF EXISTS agent_steps CASCADE;
DROP TABLE IF EXISTS agent_sessions CASCADE;
DROP TABLE IF EXISTS evaluation_results CASCADE;
DROP TABLE IF EXISTS processing_events CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS document_versions CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS episodic_memories CASCADE;
DROP TABLE IF EXISTS semantic_memories CASCADE;
DROP TABLE IF EXISTS cost_entries CASCADE;
DROP TABLE IF EXISTS tenant_budgets CASCADE;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Documents table (main document metadata)
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    project TEXT NOT NULL,
    lang TEXT NOT NULL,
    title TEXT,
    content_type TEXT,
    file_size INTEGER,
    latest_version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Document versions table
CREATE TABLE document_versions (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    sha256 TEXT,
    uri_raw TEXT,
    uri_clean TEXT,
    uri_processed TEXT,
    lang TEXT,
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    chunk_count INTEGER,
    embedding_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (doc_id, version),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- 3. Document chunks table
CREATE TABLE document_chunks (
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    lang TEXT,
    token_count INTEGER,
    char_count INTEGER,
    embedding TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chunk_id),
    FOREIGN KEY (doc_id, version) REFERENCES document_versions(doc_id, version) ON DELETE CASCADE
);

-- 4. Cost entries table
CREATE TABLE cost_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation TEXT NOT NULL,
    tenant TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    cost_amount DECIMAL(10,6) NOT NULL,
    currency TEXT DEFAULT 'USD',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Tenant budgets table
CREATE TABLE tenant_budgets (
    tenant TEXT PRIMARY KEY,
    monthly_budget DECIMAL(10,2) NOT NULL DEFAULT 100.0,
    current_usage DECIMAL(10,2) DEFAULT 0.0,
    reset_date DATE DEFAULT CURRENT_DATE + INTERVAL '1 month',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Episodic memories table
CREATE TABLE episodic_memories (
    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    embedding TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0
);

-- 7. Semantic memories table
CREATE TABLE semantic_memories (
    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    embedding TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0
);

-- 8. Agent sessions table
CREATE TABLE agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    total_cost DECIMAL(10,6) DEFAULT 0.0,
    step_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Agent steps table
CREATE TABLE agent_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,
    step_number INTEGER NOT NULL,
    tool_name TEXT,
    input_data JSONB,
    output_data JSONB,
    cost DECIMAL(10,6) DEFAULT 0.0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id) ON DELETE CASCADE
);

-- 10. Evaluation results table
CREATE TABLE evaluation_results (
    evaluation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT,
    doc_id TEXT,
    version INTEGER,
    lang TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DECIMAL(5,3),
    threshold DECIMAL(5,3),
    passed BOOLEAN,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. Processing events table
CREATE TABLE processing_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    specversion TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    datacontenttype TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
-- Documents indexes
CREATE INDEX idx_documents_tenant ON documents(tenant);
CREATE INDEX idx_documents_project ON documents(project);
CREATE INDEX idx_documents_lang ON documents(lang);

-- Document versions indexes
CREATE INDEX idx_document_versions_doc_id ON document_versions(doc_id);
CREATE INDEX idx_document_versions_status ON document_versions(processing_status);
CREATE INDEX idx_document_versions_lang ON document_versions(lang);

-- Document chunks indexes
CREATE INDEX idx_document_chunks_doc_id ON document_chunks(doc_id, version);
CREATE INDEX idx_document_chunks_chunk_id ON document_chunks(chunk_id);
CREATE INDEX idx_document_chunks_lang ON document_chunks(lang);

-- Cost entries indexes
CREATE INDEX idx_cost_entries_tenant ON cost_entries(tenant);
CREATE INDEX idx_cost_entries_operation ON cost_entries(operation);
CREATE INDEX idx_cost_entries_created ON cost_entries(created_at);

-- Memory indexes
CREATE INDEX idx_episodic_memories_tenant ON episodic_memories(tenant);
CREATE INDEX idx_semantic_memories_tenant ON semantic_memories(tenant);
CREATE INDEX idx_episodic_memories_created ON episodic_memories(created_at);
CREATE INDEX idx_semantic_memories_created ON semantic_memories(created_at);

-- Agent indexes
CREATE INDEX idx_agent_sessions_tenant ON agent_sessions(tenant);
CREATE INDEX idx_agent_steps_session ON agent_steps(session_id);

-- Verify
SELECT 'Database schema created successfully!' as status;

