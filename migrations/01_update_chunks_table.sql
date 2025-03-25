-- Update chunks table to support structured data
ALTER TABLE chunks
ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS content_type text,
ADD COLUMN IF NOT EXISTS heading_path text[];

-- Create tables for document structure
CREATE TABLE IF NOT EXISTS document_tables (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    media_id uuid REFERENCES media(id) ON DELETE CASCADE,
    table_index integer,
    content text,
    html text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_figures (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    media_id uuid REFERENCES media(id) ON DELETE CASCADE,
    figure_index integer,
    caption text,
    content text,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_structure (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    media_id uuid REFERENCES media(id) ON DELETE CASCADE,
    headings text[],
    sections jsonb,
    created_at timestamp with time zone DEFAULT now()
);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_chunks_media_id ON chunks(media_id);
CREATE INDEX IF NOT EXISTS idx_document_tables_media_id ON document_tables(media_id);
CREATE INDEX IF NOT EXISTS idx_document_figures_media_id ON document_figures(media_id);
CREATE INDEX IF NOT EXISTS idx_document_structure_media_id ON document_structure(media_id); 