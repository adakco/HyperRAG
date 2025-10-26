-- HyperRAG Database Schema
-- Create tables for all services

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Documents table (for ingestor)
CREATE TABLE IF NOT EXISTS documents (
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

-- Document versions table (for ingestor)
CREATE TABLE IF NOT EXISTS document_versions (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    sha256 TEXT,
    uri_raw TEXT,
    uri_clean TEXT,
    uri_processed TEXT,
    lang TEXT,
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (doc_id, version)
);

-- Chunks table (for chunker)
CREATE TABLE IF NOT EXISTS document_chunks (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    chunk_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    lang TEXT,
    token_count INTEGER,
    embedding TEXT, -- JSON string for embedding vector
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (doc_id, version, chunk_id)
);

-- Cost entries table (for costing)
CREATE TABLE IF NOT EXISTS cost_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation TEXT NOT NULL,
    tenant TEXT NOT NULL,
    amount DECIMAL(10,6) NOT NULL,
    currency TEXT DEFAULT 'USD',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tenant budgets table (for costing)
CREATE TABLE IF NOT EXISTS tenant_budgets (
    tenant TEXT PRIMARY KEY,
    monthly_budget DECIMAL(10,2) NOT NULL DEFAULT 100.0,
    current_usage DECIMAL(10,2) DEFAULT 0.0,
    reset_date DATE DEFAULT CURRENT_DATE + INTERVAL '1 month',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Episodic memories table (for memory)
CREATE TABLE IF NOT EXISTS episodic_memories (
    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    embedding TEXT,  -- JSON string for embedding vector
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0
);

-- Semantic memories table (for memory)
CREATE TABLE IF NOT EXISTS semantic_memories (
    memory_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    embedding TEXT,  -- JSON string for embedding vector
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0
);

-- Agent sessions table (for agent-orch)
CREATE TABLE IF NOT EXISTS agent_sessions (
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

-- Agent steps table (for agent-orch)
CREATE TABLE IF NOT EXISTS agent_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES agent_sessions(session_id),
    step_number INTEGER NOT NULL,
    tool_name TEXT,
    input_data JSONB,
    output_data JSONB,
    cost DECIMAL(10,6) DEFAULT 0.0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
);

-- Evaluation results table (for evaluator)
CREATE TABLE IF NOT EXISTS evaluation_results (
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

-- Processing events table (for ingestor)
CREATE TABLE IF NOT EXISTS processing_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    specversion TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    datacontenttype TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project);
CREATE INDEX IF NOT EXISTS idx_document_versions_doc_id ON document_versions(doc_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_status ON document_versions(processing_status);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks(doc_id, version);
CREATE INDEX IF NOT EXISTS idx_cost_entries_tenant ON cost_entries(tenant);
CREATE INDEX IF NOT EXISTS idx_cost_entries_operation ON cost_entries(operation);
CREATE INDEX IF NOT EXISTS idx_episodic_memories_tenant ON episodic_memories(tenant);
CREATE INDEX IF NOT EXISTS idx_semantic_memories_tenant ON semantic_memories(tenant);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_tenant ON agent_sessions(tenant);
CREATE INDEX IF NOT EXISTS idx_agent_steps_session ON agent_steps(session_id);
