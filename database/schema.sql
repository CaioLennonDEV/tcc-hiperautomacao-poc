-- ========================================================
-- Schema SQL: Prova de Conceito de Hiperautomação (GLPI / TCC)
-- Tabela de Auditoria e Persistência de Triagem
-- Banco: Supabase / PostgreSQL
-- ========================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS chamados_triagem (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    glpi_ticket_id INTEGER,
    remetente_email TEXT NOT NULL,
    conteudo_original TEXT NOT NULL,
    intencao_classificada TEXT NOT NULL,   -- 'Duvida', 'Incidente', 'Solicitacao', 'Outros'
    nivel_urgencia TEXT NOT NULL,          -- 'Baixa', 'Media', 'Alta', 'Critica'
    categoria_sugerida TEXT,               -- 'Hardware', 'Software', 'Redes', 'Acessos'
    confianca_ia NUMERIC(3,2) NOT NULL,    -- Score probabilístico entre 0.00 e 1.00
    status_processamento TEXT NOT NULL,    -- 'Automatico' ou 'Revisao Humana'
    resposta_sugerida TEXT,
    requer_revisao_humana BOOLEAN DEFAULT FALSE,
    tempo_processamento_ms INTEGER
);

-- Índices para otimização de consultas e auditoria
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_status ON chamados_triagem(status_processamento);
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_intencao ON chamados_triagem(intencao_classificada);
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_created_at ON chamados_triagem(created_at DESC);
