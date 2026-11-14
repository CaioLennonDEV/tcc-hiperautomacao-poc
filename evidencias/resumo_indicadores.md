# Resumo de Conferência e Cálculo dos Indicadores da PoC

## 1. Transparência sobre a Origem dos Dados e Execuções
Para fins de auditoria acadêmica, distinguem-se explicitamente as três fontes de evidência deste repositório:
1. **Conjunto de Entrada e Gabarito Sintético (`data/chamados_sinteticos_100.json`, `data/gabarito_classificacao_100.csv`):** 100 chamados fictícios anonimizados (25 Hardware, 25 Software, 25 Redes e 25 Acessos; sendo 80 padronizados e 20 ambíguos/críticos), criados sem dados reais de usuários.
2. **Snapshot Determinístico em SQL (`database/schema.sql` e `evidencias/resultados_execucao_100.*`):** Carga SQL reproduzível que consolida os 100 registros de exemplo na tabela `chamados_triagem` para verificação exata dos indicadores descritos no artigo (74 acertos em 80 padronizados, 82 automáticos e 18 em revisão humana). Não representa 100 chamadas pagas executadas em ambiente produtivo real.
3. **Execução Real da Camada de Roteamento e Emulação HTTP (`evidencias/testes_valor_limite_httpbin.json`):** Validação executada via requisição HTTP POST real para `https://httpbin.org/post` (o mesmo endpoint configurado nos nós HTTP do fluxo [`n8n-workflows/triagem-chamados-workflow.json`](../n8n-workflows/triagem-chamados-workflow.json)), comprovando o comportamento do gateway condicional nos limites `0,84`, `0,85`, `0,86` e no caso crítico com confiança alta (`0,92` + `requer_revisao_humana = true`).

> **Nota sobre o tempo de processamento:** Os valores de `tempo_processamento_ms` presentes no snapshot SQL são referências sintéticas de demonstração. Conforme explicitado na Seção 4.2.3 do artigo (p. 23), o tempo médio de `1,9 s` informado em versão preliminar não foi mantido como medição consolidada de desempenho real.

---

## 2. Configuração Técnica Conferida
- **Modelo LLM no fluxo n8n:** `models/gemini-3.5-flash-lite`
- **Temperatura:** `0`
- **Parser JSON:** `@n8n/n8n-nodes-langchain.outputParserStructured`
- **Limiar de confiança no nó IF:** `0.85` (combinado com `requer_revisao_humana == false`)
- **Endpoints de emulação GLPI:** `https://httpbin.org/post` (ramo automático) e `https://httpbin.org/post` (ramo revisão humana)
- **Varredura de segredos/tokens nos artefatos:** Limpa (`secret_scan_clean = True`)

---

## 3. Indicadores Consolidados (`N = 100`)

| Indicador | Fórmula / Critério | Resultado Conferido |
| :--- | :--- | :--- |
| Total de chamados sintéticos | `COUNT(*)` | **100** (25 Hardware, 25 Software, 25 Redes, 25 Acessos) |
| Cenários padronizados | `ticket_id` 2001..2080 | **80** (20 por categoria) |
| Cenários ambíguos / críticos | `ticket_id` 2081..2100 | **20** (5 por categoria) |
| Acertos categoriais (padronizados) | `categoria_sugerida == categoria_gabarito` em 2001..2080 | **74 de 80 (92.5%)** |
| Divergências limítrofes (padronizados) | `categoria_sugerida != categoria_gabarito` em 2001..2080 | **6 de 80 (7.5%)** |
| Encaminhamentos automáticos | `confianca_ia >= 0.85 AND requer_revisao_humana = FALSE` | **82 de 100 (82,0%)** |
| Encaminhamentos para revisão humana | `confianca_ia < 0.85 OR requer_revisao_humana = TRUE` | **18 de 100 (18,0%)** |

---

## 4. Matriz de Confusão dos 80 Casos Padronizados (`2001..2080`)

| Gabarito \ Predição | Hardware | Software | Redes | Acessos | Total Gabarito |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Hardware** | 18 | 0 | 2 | 0 | 20 |
| **Software** | 0 | 20 | 0 | 0 | 20 |
| **Redes** | 0 | 0 | 19 | 1 | 20 |
| **Acessos** | 0 | 3 | 0 | 17 | 20 |

### Detalhamento das 6 Divergências Semânticas (80 - 74 = 6)

| Ticket ID | Relato | Gabarito | Sugerida | Confiança | Roteamento |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 2015 | Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura. | Acessos | Software | 0.88 | Automatico |
| 2028 | Impressora do 2º andar atolada - Apresentando erro de bandeja e não puxa papel. | Hardware | Redes | 0.88 | Automatico |
| 2042 | VPN desconectando - Erro de autenticação SSL ao conectar de home office. | Redes | Acessos | 0.89 | Automatico |
| 2055 | Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura. | Acessos | Software | 0.89 | Automatico |
| 2068 | Impressora do 2º andar atolada - Apresentando erro de bandeja e não puxa papel. | Hardware | Redes | 0.89 | Automatico |
| 2079 | Solicitação de acesso ao ERP - Novo colaborador do financeiro precisa de perfil de leitura. | Acessos | Software | 0.87 | Automatico |

---

## 5. Validação dos Testes de Valor-Limite e Caso Crítico (`httpbin.org/post`)

| Ticket ID | Cenário de Teste | Confiança | `requer_revisao_humana` | Decisão Gateway | Resposta HTTP Emulada |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 2001 | Cenário padronizado N1 | 0.95 | `false` | Automatico | HTTP 200 (512.07 ms) |
| 2080 | Caso A (Limite superior: 0.86) | 0.86 | `false` | Automatico | HTTP 200 (427.15 ms) |
| 2081 | Caso B (No limiar exato: 0.85) | 0.85 | `false` | Automatico | HTTP 200 (531.8 ms) |
| 2084 | Caso C (Abaixo do limiar: 0.84) | 0.84 | `true` | Revisao Humana | HTTP 200 (453.85 ms) |
| 2085 | Caso D (Crítico com confiança alta: 0.92 + revisão obrigatória) | 0.92 | `true` | Revisao Humana | HTTP 200 (470.57 ms) |
