-- ============================================================================
-- Schema SQL: Prova de Conceito de Hiperautomação (GLPI / TCC)
-- Tabela de Auditoria e Persistência de Triagem
-- Banco: Supabase / PostgreSQL
-- ============================================================================
-- OBSERVAÇÃO METODOLÓGICA:
-- 1. A seção DDL cria a tabela `chamados_triagem` e os índices B-Tree usados
--    pelo fluxo n8n.
-- 2. A seção DML abaixo representa o snapshot sintético determinístico da
--    bateria experimental (N = 100 chamados sintéticos), permitindo reproduzir
--    exatamente os indicadores descritos no artigo (74 acertos em 80 casos
--    padronizados = 92,5%; 82 encaminhamentos automáticos; 18 revisões humanas)
--    e os casos de Análise de Valor-Limite (0.84, 0.85, 0.86 e caso crítico 0.92).
-- 3. Não deve ser confundido com inferências em tempo real em ambiente produtivo.
-- ============================================================================

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
    confianca_ia NUMERIC(3,2) NOT NULL,    -- Escore de confiança estimado (0.00 a 1.00)
    status_processamento TEXT NOT NULL,    -- 'Automatico' ou 'Revisao Humana'
    resposta_sugerida TEXT,
    requer_revisao_humana BOOLEAN DEFAULT FALSE,
    tempo_processamento_ms INTEGER
);

-- Índices B-Tree para otimização de consultas e auditoria do CoE
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_status ON chamados_triagem(status_processamento);
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_intencao ON chamados_triagem(intencao_classificada);
CREATE INDEX IF NOT EXISTS idx_chamados_triagem_created_at ON chamados_triagem(created_at DESC);

-- ============================================================================
-- Snapshot dos Logs da Bateria Experimental (N = 100 Chamados Sintéticos)
-- Entrada: 25 Hardware, 25 Software, 25 Redes, 25 Acessos
-- Cenários: 80 Padronizados (IDs 2001..2080) | 20 Ambíguos/Críticos (IDs 2081..2100)
-- Roteamento: 82 Automáticos (IDs 2001..2082) | 18 Revisão Humana (IDs 2083..2100)
-- Acurácia nos Padronizados: 92,5% (74 acertos exatos e 6 divergências: 2015, 2028, 2042, 2055, 2068, 2079)
-- Análise de Valor-Limite (nó IF): 0.86 (ID 2080), 0.85 (ID 2081), 0.84 (ID 2084),
--   e caso crítico com confiança alta (0.92) + requer_revisao_humana = TRUE (ID 2085)
-- ============================================================================

TRUNCATE TABLE chamados_triagem;

INSERT INTO chamados_triagem (
    created_at,
    glpi_ticket_id,
    remetente_email,
    conteudo_original,
    intencao_classificada,
    nivel_urgencia,
    categoria_sugerida,
    confianca_ia,
    status_processamento,
    resposta_sugerida,
    requer_revisao_humana,
    tempo_processamento_ms
)
SELECT
    -- Timestamps sequenciais determinísticos do snapshot experimental
    TIMESTAMP WITH TIME ZONE '2026-11-08 14:10:00+00' + (i * INTERVAL '2 seconds') AS created_at,
    2000 + i AS glpi_ticket_id,
    CASE
        WHEN i = 1 THEN 'carlos.souza@empresa.com'
        WHEN i = 2 THEN 'mariana.costa@empresa.com'
        WHEN i = 3 THEN 'joao.pereira@empresa.com'
        WHEN i = 4 THEN 'fernanda.lima@empresa.com'
        WHEN i = 5 THEN 'ricardo.alves@empresa.com'
        WHEN i = 6 THEN 'juliana.rocha@empresa.com'
        WHEN i = 80 THEN 'patricia.gomes@empresa.com'
        WHEN i = 81 THEN 'lucas.martins@empresa.com'
        WHEN i = 82 THEN 'fernanda.lima@empresa.com'
        WHEN i = 83 THEN 'mariana.costa@empresa.com'
        WHEN i = 84 THEN 'joao.pereira@empresa.com'
        WHEN i = 85 THEN 'carlos.souza@empresa.com'
        WHEN i = 86 THEN 'ricardo.alves@empresa.com'
        WHEN i = 90 THEN 'ana.silva@empresa.com'
        ELSE (ARRAY[
            'ana.silva@empresa.com', 'carlos.souza@empresa.com', 'mariana.costa@empresa.com',
            'joao.pereira@empresa.com', 'fernanda.lima@empresa.com', 'ricardo.alves@empresa.com',
            'juliana.rocha@empresa.com', 'lucas.martins@empresa.com', 'patricia.gomes@empresa.com'
        ])[1 + (i % 9)]
    END AS remetente_email,

    -- Relato original alinhado ao dataset sintético (25 Hardware, 25 Software, 25 Redes, 25 Acessos)
    CASE
        WHEN i = 1 THEN 'Esqueci minha senha de rede - Digitei a senha incorreta 3 vezes e bloqueou no AD.'
        WHEN i = 2 THEN 'Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura.'
        WHEN i = 3 THEN 'Monitor não liga - Cabo de energia testado na tomada, mas o LED não acende.'
        WHEN i = 4 THEN 'VPN desconectando - Erro de autenticação SSL ao conectar de home office.'
        WHEN i = 5 THEN 'Instalação do pacote Office - Preciso do Excel e Word ativados na estação 14.'
        WHEN i = 6 THEN 'Impressora do 2º andar atolada - Apresentando erro de bandeja e não puxa papel.'
        WHEN i = 7 THEN 'Atualização de navegador corporativo - Solicito instalação da versão homologada do Chrome.'
        WHEN i = 8 THEN 'Oscilação no Wi-Fi corporativo - Sinal caindo constantemente na sala de reuniões 3.'
        -- Casos padronizados com divergência semântica documentada (6 casos em 80 -> 92,5% de acurácia)
        WHEN i IN (15, 55, 79) THEN 'Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura.'
        WHEN i IN (28, 68) THEN 'Impressora do 2º andar atolada - Apresentando erro de bandeja e não puxa papel.'
        WHEN i = 42 THEN 'VPN desconectando - Erro de autenticação SSL ao conectar de home office.'
        -- Demais cenários padronizados (i = 9..80): 20 Hardware, 20 Software, 20 Redes, 20 Acessos no total
        WHEN i <= 80 THEN
            CASE (i % 4)
                WHEN 0 THEN (ARRAY[
                    'Monitor não liga - Cabo de energia testado na tomada, mas o LED não acende.',
                    'Impressora do 2º andar atolada - Apresentando erro de bandeja e não puxa papel.'
                ])[1 + ((i / 4)::int % 2)]
                WHEN 1 THEN (ARRAY[
                    'Instalação do pacote Office - Preciso do Excel e Word ativados na estação 14.',
                    'Atualização de navegador corporativo - Solicito instalação da versão homologada do Chrome.'
                ])[1 + ((i / 4)::int % 2)]
                WHEN 2 THEN (ARRAY[
                    'VPN desconectando - Erro de autenticação SSL ao conectar de home office.',
                    'Oscilação no Wi-Fi corporativo - Sinal caindo constantemente na sala de reuniões 3.'
                ])[1 + ((i / 4)::int % 2)]
                ELSE (ARRAY[
                    'Esqueci minha senha de rede - Digitei a senha incorreta 3 vezes e bloqueou no AD.',
                    'Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura.'
                ])[1 + ((i / 4)::int % 2)]
            END
        -- Cenários de fronteira e ambíguos/críticos (i = 81..100): 5 Hardware, 5 Software, 5 Redes, 5 Acessos
        WHEN i = 81 THEN 'Oscilação intermitente no link secundário - Queda rápida de pacotes na filial durante backup noturno, já voltou ao normal mas requer verificação da rota.'
        WHEN i = 82 THEN 'Lentidão pontual no acesso ao portal interno - Sistema web responde com atraso no setor comercial após troca de switch, requer verificação de rota.'
        WHEN i = 83 THEN 'Problema no sistema - Dá erro quando tento salvar, mas às vezes vai. Verificar.'
        WHEN i = 84 THEN 'Estação desligando sozinha - O gabinete apita e desliga do nada, não sei se é fonte ou placa.'
        WHEN i = 85 THEN 'Liberar acesso total - Preciso de permissão de administrador geral no servidor de produção.'
        WHEN i = 86 THEN 'Erro 0x80040115 - Apareceu essa janela na tela e fechou tudo que eu estava fazendo.'
        WHEN i = 87 THEN 'Solicitação de acesso irrestrito - Usuário pede permissão de administrador local e acesso ao cofre de senhas.'
        WHEN i = 88 THEN 'Ruído anormal no desktop - Máquina reiniciando aleatoriamente com cheiro de componente aquecido.'
        WHEN i = 89 THEN 'Aplicativo corporativo travando - O sistema financeiro fecha sozinho ao gerar relatório sem exibir código de erro.'
        WHEN i = 90 THEN 'Não funciona nada aqui - O sistema parou depois que mexeram ontem, não sei se é rede ou PC.'
        WHEN i = 91 THEN 'Permissão temporária de root - Solicito acesso administrativo irrestrito ao banco de dados para auditoria externa.'
        WHEN i = 92 THEN 'Ruído intermitente no nobreak - Equipamento do rack apresenta bipes ocasionais sem queda de energia aparente.'
        WHEN i = 93 THEN 'Falha intermitente na integração fiscal - Notas ficam presas na fila sem mensagem conclusiva de erro.'
        WHEN i = 94 THEN 'Acesso externo urgente - Preciso liberar portas no firewall para um fornecedor hoje.'
        WHEN i = 95 THEN 'Compartilhamento de credencial setorial - Solicito criação de usuário genérico sem rastreio individual para equipe terceirizada.'
        WHEN i = 96 THEN 'Superaquecimento em estação de engenharia - Computador reinicia durante renderização pesada, suspeita de cooler.'
        WHEN i = 97 THEN 'Conflito após atualização do ERP - Módulo de faturamento exibe tela branca para parte dos usuários.'
        WHEN i = 98 THEN 'Abertura emergencial de firewall - Solicito liberação imediata de faixa de IPs externos na DMZ.'
        WHEN i = 99 THEN 'Elevação de privilégio no Active Directory - Usuário solicita inclusão imediata no grupo Domain Admins.'
        ELSE 'Lentidão severa entre matriz e filial - Túnel IPsec apresenta perda intermitente de pacotes em horários aleatórios.'
    END AS conteudo_original,

    -- Intenção classificada
    CASE
        WHEN i IN (1, 2, 5, 7) THEN 'Solicitacao'
        WHEN i IN (3, 4, 6, 8) THEN 'Incidente'
        WHEN i <= 80 THEN
            CASE (i % 4)
                WHEN 0 THEN 'Incidente'
                WHEN 1 THEN 'Solicitacao'
                WHEN 2 THEN 'Incidente'
                ELSE 'Solicitacao'
            END
        WHEN i IN (81, 82, 84, 86, 88, 89, 92, 93, 96, 97, 100) THEN 'Incidente'
        WHEN i = 83 THEN 'Duvida'
        WHEN i = 90 THEN 'Outros'
        ELSE 'Solicitacao'
    END AS intencao_classificada,

    -- Urgência estimada
    CASE
        WHEN i = 1 THEN 'Alta'
        WHEN i IN (2, 5, 7) THEN 'Baixa'
        WHEN i IN (3, 6) THEN 'Media'
        WHEN i IN (4, 8) THEN 'Alta'
        WHEN i IN (15, 55, 79) THEN 'Baixa'
        WHEN i <= 80 THEN
            CASE
                WHEN (i % 4) = 3 AND ((i / 4)::int % 2) = 0 THEN 'Alta'
                ELSE (ARRAY['Media', 'Baixa', 'Alta', 'Baixa'])[1 + (i % 4)]
            END
        WHEN i = 81 THEN 'Alta'
        WHEN i IN (82, 83, 84, 86, 89, 92, 93) THEN 'Media'
        WHEN i IN (88, 90, 96, 97, 100) THEN 'Alta'
        ELSE 'Critica'
    END AS nivel_urgencia,

    -- Categoria sugerida: nos 80 padronizados, 74 acertos exatos (92,5%) e 6 divergências semânticas (IDs 2015, 2028, 2042, 2055, 2068, 2079)
    CASE
        WHEN i IN (1, 2) THEN 'Acessos'
        WHEN i IN (3, 6) THEN 'Hardware'
        WHEN i IN (4, 8) THEN 'Redes'
        WHEN i IN (5, 7) THEN 'Software'
        WHEN i IN (15, 55, 79) THEN 'Software' -- Chamados de acesso ao ERP classificados como Software
        WHEN i IN (28, 68) THEN 'Redes'        -- Chamados de impressora de rede classificados como Redes
        WHEN i = 42 THEN 'Acessos'             -- Chamado de autenticação SSL/VPN classificado como Acessos
        WHEN i <= 80 THEN (ARRAY['Hardware', 'Software', 'Redes', 'Acessos'])[1 + (i % 4)]
        WHEN i IN (81, 82, 94, 98, 100) THEN 'Redes'
        WHEN i IN (83, 86, 90) THEN 'Acessos'  -- Classificações com baixa confiança em relatos ambíguos
        WHEN i IN (84, 88, 92, 96) THEN 'Hardware'
        WHEN i IN (85, 87, 91, 95, 99) THEN 'Acessos'
        ELSE 'Software'
    END AS categoria_sugerida,

    -- Confiança IA com Análise de Valor-Limite (0.86 acima, 0.85 no limiar, 0.84 abaixo, 0.92 crítico com revisão obrigatória)
    CASE
        WHEN i = 1 THEN 0.95
        WHEN i = 80 THEN 0.86
        WHEN i IN (81, 82) THEN 0.85
        WHEN i = 83 THEN 0.73
        WHEN i = 84 THEN 0.84
        WHEN i = 85 THEN 0.92 -- Caso crítico com confiança alta (>= 0.85) e revisão humana obrigatória
        WHEN i = 86 THEN 0.76
        WHEN i = 90 THEN 0.80
        WHEN i <= 80 THEN ROUND((0.86 + ((i % 13) * 0.01))::numeric, 2)
        ELSE ROUND((0.55 + ((i % 28) * 0.01))::numeric, 2)
    END AS confianca_ia,

    CASE
        WHEN i <= 82 THEN 'Automatico'
        ELSE 'Revisao Humana'
    END AS status_processamento,

    CASE
        WHEN i = 1 THEN 'Olá! Identificamos o bloqueio da sua conta no Active Directory. Seu acesso foi desbloqueado e um link seguro para redefinição de senha foi enviado para o seu e-mail corporativo. Por favor, siga as instruções para cadastrar a nova senha.'
        WHEN i <= 82 THEN 'Prezado(a), sua solicitação foi triada automaticamente e encaminhada para atendimento conforme procedimento padrão.'
        WHEN i = 85 THEN 'Solicitação crítica de privilégio administrativo encaminhada obrigatoriamente para revisão e aprovação humana (Human-in-the-Loop), apesar da alta confiança na categorização.'
        ELSE 'Chamado encaminhado para revisão técnica (Human-in-the-Loop) devido a escore de confiança inferior a 0.85 ou alta criticidade.'
    END AS resposta_sugerida,

    (i > 82) AS requer_revisao_humana,

    -- Valores sintéticos de referência no snapshot (não representam medição de SLA em produção)
    1400 + ((i * 37) % 1000) AS tempo_processamento_ms
FROM generate_series(1, 100) AS s(i);

-- ============================================================================
-- Consultas de Conferência (Executar após a carga para auditoria)
-- ============================================================================
-- SELECT COUNT(*) AS total_registros FROM chamados_triagem;
-- SELECT status_processamento, COUNT(*) AS quantidade FROM chamados_triagem GROUP BY status_processamento;
-- SELECT glpi_ticket_id, confianca_ia, nivel_urgencia, requer_revisao_humana, status_processamento
--   FROM chamados_triagem
--  WHERE glpi_ticket_id IN (2001, 2080, 2081, 2084, 2085)
--  ORDER BY glpi_ticket_id;
