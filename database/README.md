# Camada de Persistência — Supabase / PostgreSQL (`database/schema.sql`)

Este diretório documenta a estrutura relacional e a carga sintética da tabela `chamados_triagem`, utilizada pela Prova de Conceito (PoC) para persistência dos registros de triagem.

## Diagrama da Tabela Relacional e Índices B-Tree

![Estrutura Relacional de Persistência e Auditoria](../docs/imagens/diagrama_er_chamados_triagem.png)

## Resumo do Esquema (`schema.sql`)
- **Extensão:** `pgcrypto` (habilita `gen_random_uuid()` para chaves primárias UUID).
- **Tabela:** `public.chamados_triagem` (13 colunas cobrindo metadados do chamado, entrada textual, saída estruturada da camada cognitiva, decisão de roteamento e referência de latência).
- **Índices B-Tree:**
  - `idx_chamados_triagem_status` em `(status_processamento)`
  - `idx_chamados_triagem_intencao` em `(intencao_classificada)`
  - `idx_chamados_triagem_created_at` em `(created_at DESC)`
- **Idempotência:** O DDL utiliza `CREATE EXTENSION IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS` e `TRUNCATE TABLE` antes do `INSERT` sintético, podendo ser reexecutado sem erros no SQL Editor do Supabase ou em qualquer instância PostgreSQL compatível.

## Distinção entre DDL e Snapshot Sintético
- As instruções `CREATE TABLE` e `CREATE INDEX` definem a estrutura real usada pelo nó `Registra Auditoria no Supabase` do fluxo [`n8n-workflows/triagem-chamados-workflow.json`](../n8n-workflows/triagem-chamados-workflow.json).
- O bloco `INSERT INTO chamados_triagem ... FROM generate_series(1, 100)` insere um **snapshot determinístico de 100 registros sintéticos** que reproduz exatamente os indicadores descritos no artigo (`74` acertos em `80` casos padronizados = `92,5%`; `82` encaminhamentos automáticos e `18` em revisão humana) e os testes de valor-limite (`0,84`, `0,85`, `0,86` e caso crítico `0,92`).
