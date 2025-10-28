-- Fix HyperRAG Database Schema
-- Add missing columns and indexes

-- Add missing columns to document_versions
DO $$ 
BEGIN
    -- Add chunk_count if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'document_versions' 
                   AND column_name = 'chunk_count') THEN
        ALTER TABLE document_versions ADD COLUMN chunk_count INTEGER;
    END IF;

    -- Add embedding_count if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'document_versions' 
                   AND column_name = 'embedding_count') THEN
        ALTER TABLE document_versions ADD COLUMN embedding_count INTEGER;
    END IF;
END $$;

-- Add missing column to document_chunks
DO $$ 
BEGIN
    -- Add char_count if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'document_chunks' 
                   AND column_name = 'char_count') THEN
        ALTER TABLE document_chunks ADD COLUMN char_count INTEGER;
    END IF;
END $$;

-- Create missing indexes
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_id ON document_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_lang ON document_versions(lang);
CREATE INDEX IF NOT EXISTS idx_document_chunks_lang ON document_chunks(lang);

-- Verify the fixes
SELECT 
    'document_versions' as table_name,
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'document_versions'
ORDER BY ordinal_position;

SELECT 
    'document_chunks' as table_name,
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'document_chunks'
ORDER BY ordinal_position;

