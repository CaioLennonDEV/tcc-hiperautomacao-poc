# System Prompt e Análise de Valor-Limite (*Boundary Value Analysis*) — Triagem Cognitiva de Chamados (GLPI)

## 1. Configuração Técnica do Agente no n8n
- **Workflow exportado:** [`n8n-workflows/triagem-chamados-workflow.json`](../n8n-workflows/triagem-chamados-workflow.json)
- **Nó de modelo:** `Google Gemini Chat Model` (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`, `typeVersion: 1.2`)
- **Identificador do modelo:** `models/gemini-3.5-flash-lite`
- **Temperatura:** `0` (`0.0` — geração determinística)
- **Parser estruturado:** `Structured Output Parser` (`@n8n/n8n-nodes-langchain.outputParserStructured`, `typeVersion: 1.3`)
- **Gateway condicional:** `Verifica Confianca (Score >= 0.85)` — exige simultaneamente `requer_revisao_humana == false` e `confianca >= 0.85` para encaminhamento automático.

## 2. Papel e Instrução Diretiva (System Prompt)
Texto completo configurado em `Agente Cognitivo LLM (Parsing)` (`@n8n/n8n-nodes-langchain.agent`, `typeVersion: 1.7`, `options.systemMessage`):

```text
Você é um classificador determinístico para triagem inicial de chamados do GLPI integrado à esteira de hiperautomação. Analise apenas os dados informados no chamado, sem inventar dados técnicos ausentes.

Retorne ESTRITAMENTE em formato JSON (via Structured Output Parser) com as chaves:
- intencao: "Incidente" (falha, erro, travamento, queda, mau funcionamento), "Solicitacao" (pedido de acesso, criação de usuário, instalação, atualização, liberação), "Duvida" (pedido de esclarecimento sem erro objetivo claro) ou "Outros" (relato excessivamente genérico sem causa identificável).
- urgencia: "Baixa", "Media", "Alta" ou "Critica".
- categoria_glpi: estritamente "Acessos", "Hardware", "Redes" ou "Software".
- confianca: número decimal de 0.0 a 1.0 refletindo a clareza e previsibilidade da classificação.
- resumo_demanda: síntese objetiva em 1 linha.
- resposta_sugerida: mensagem cordial de primeiro contato informando apenas a triagem e o encaminhamento (NUNCA afirme que conta já foi desbloqueada, e-mail já foi enviado, firewall já foi liberado ou instalação já foi concluída).
- requer_revisao_humana: booleano obrigatório. Marque true sempre que confianca < 0.85, houver ambiguidade entre componentes/causas (ex.: relato vago sem código de erro conclusivo ou sem definição entre hardware/sistema/rede), ou risco crítico de segurança/infraestrutura (ex.: permissão de administrador/root/Domain Admins, acesso ao cofre de senhas, usuário genérico sem rastreio, liberação de firewall/DMZ, superaquecimento, cheiro de componente aquecido, falha em nobreak de rack ou erro em integração fiscal/faturamento). Para chamados padronizados e claros de suporte operacional (ex.: senha bloqueada no AD, perfil de leitura no ERP, monitor sem ligar com cabo testado, atolamento de papel em impressora, instalação de Office/Chrome, VPN/Wi-Fi pontual), atribua confianca >= 0.85 e requer_revisao_humana: false.
```

## 3. Regras de Execução e Metodologia de Limiar (Análise de Valor-Limite)
1. Responder exclusivamente em JSON válido conforme o esquema definido no *Structured Output Parser*, sem texto adicional ou blocos externos.
2. Não inventar configurações de infraestrutura ou dados técnicos ausentes no relato original.
3. Aplicar a **Análise de Valor-Limite (*Boundary Value Analysis*)** sobre o limiar `0.85` no nó condicional (`Verifica Confianca (Score >= 0.85)`), cobrindo quatro casos de fronteira e exceção crítica:
   - **Caso A (Acima do Limiar — `confianca = 0.86`, `requer_revisao_humana = false`):** Demanda padronizada e clara -> **Roteamento Automático** (`Atualiza Chamado no GLPI (API)`).
   - **Caso B (No Limiar Exato — `confianca = 0.85`, `requer_revisao_humana = false`):** Demanda com informação suficiente no limite operacional -> **Roteamento Automático** (`Atualiza Chamado no GLPI (API)`).
   - **Caso C (Abaixo do Limiar — `confianca = 0.84`, `requer_revisao_humana = true`):** Demanda com ambiguidade ou escore imediatamente abaixo de `0.85` -> **Revisão Humana** (`Desvio para Fila Humana (Human-in-the-Loop)`).
   - **Caso D (Crítico com Confiança Alta — `confianca = 0.92`, `requer_revisao_humana = true`):** Solicitação de alto risco/criticidade (ex.: permissão de administrador geral em servidor de produção ou liberação de firewall/root). Mesmo com escore de confiança acima de `0.85`, a condição booleana `requer_revisao_humana == false` falha no nó IF e o chamado segue obrigatoriamente para **Revisão Humana** (`Desvio para Fila Humana (Human-in-the-Loop)`).

## 4. Esquema JSON de Saída (*Structured Output Parser*)
```json
{
  "intencao": "Duvida | Incidente | Solicitacao | Outros",
  "urgencia": "Baixa | Media | Alta | Critica",
  "categoria_glpi": "Hardware | Software | Redes | Acessos",
  "confianca": 0.95,
  "resumo_demanda": "Síntese concisa de 1 linha sobre a necessidade",
  "resposta_sugerida": "Texto de primeiro contato/orientação técnica para o solicitante",
  "requer_revisao_humana": false
}
```

## 5. Casos de Teste de Limite e Exemplos de Payloads (Entrada e Saída Estruturada)

### 5.1 Casos de Teste de Limite (`0.86`, `0.85`, `0.84` e Caso Crítico `0.92`)
Os payloads abaixo e os logs das requisições `HTTP POST` disparadas **diretamente pelo script Python ([`../scripts/validar_poc.py`](../scripts/validar_poc.py))** contra `https://httpbin.org/post` estão registrados em [`../evidencias/testes_valor_limite_httpbin.json`](../evidencias/testes_valor_limite_httpbin.json). Como a inferência real do Gemini nos 100 chamados retornou escores em múltiplos de `0,05` (`0,50` a `1,00`), esses testes exercitam via Python os exatos valores de fronteira (`0,84`, `0,85`, `0,86` e `0,92`) para validar a lógica do gateway (`executado_no_n8n = false`, `inferencia_gemini_real = false`), complementando os 100 logs reais exportados do n8n em [`../evidencias/logs_execucao_n8n_100.json`](../evidencias/logs_execucao_n8n_100.json).

```json
[
  {
    "caso_teste": "Limite Superior (confianca = 0.86)",
    "input": {
      "ticket_id": 2080,
      "user_email": "patricia.gomes@empresa.com",
      "ticket_title": "Solicitação de acesso ao ERP",
      "ticket_description": "Novo colaborador do financeiro precisa de perfil de leitura."
    },
    "output_parser": {
      "intencao": "Solicitacao",
      "urgencia": "Baixa",
      "categoria_glpi": "Acessos",
      "confianca": 0.86,
      "resumo_demanda": "Solicitação de perfil de leitura no ERP para novo colaborador do setor financeiro.",
      "resposta_sugerida": "Prezado(a), sua solicitação foi triada automaticamente e encaminhada para atendimento conforme procedimento padrão.",
      "requer_revisao_humana": false
    },
    "decisao_gateway_n8n": "Automatico"
  },
  {
    "caso_teste": "Limite Exato (confianca = 0.85)",
    "input": {
      "ticket_id": 2081,
      "user_email": "lucas.martins@empresa.com",
      "ticket_title": "Oscilação intermitente no link secundário",
      "ticket_description": "Queda rápida de pacotes na filial durante backup noturno, já voltou ao normal mas requer verificação da rota."
    },
    "output_parser": {
      "intencao": "Incidente",
      "urgencia": "Alta",
      "categoria_glpi": "Redes",
      "confianca": 0.85,
      "resumo_demanda": "Oscilação intermitente com queda de pacotes no link secundário da filial durante backup noturno.",
      "resposta_sugerida": "Prezado(a), sua solicitação foi triada automaticamente e encaminhada para atendimento conforme procedimento padrão.",
      "requer_revisao_humana": false
    },
    "decisao_gateway_n8n": "Automatico"
  },
  {
    "caso_teste": "Limite Inferior (confianca = 0.84)",
    "input": {
      "ticket_id": 2084,
      "user_email": "joao.pereira@empresa.com",
      "ticket_title": "Estação desligando sozinha",
      "ticket_description": "O gabinete apita e desliga do nada, não sei se é fonte ou placa."
    },
    "output_parser": {
      "intencao": "Incidente",
      "urgencia": "Media",
      "categoria_glpi": "Hardware",
      "confianca": 0.84,
      "resumo_demanda": "Estação de trabalho desligando repentinamente com sinal sonoro, sem diagnóstico conclusivo entre fonte e placa.",
      "resposta_sugerida": "Chamado encaminhado para revisão técnica (Human-in-the-Loop) devido a escore de confiança inferior a 0.85 ou alta criticidade.",
      "requer_revisao_humana": true
    },
    "decisao_gateway_n8n": "Revisao Humana"
  },
  {
    "caso_teste": "Caso Crítico com Confiança Alta (confianca = 0.92, revisao obrigatoria)",
    "input": {
      "ticket_id": 2085,
      "user_email": "carlos.souza@empresa.com",
      "ticket_title": "Liberar acesso total",
      "ticket_description": "Preciso de permissão de administrador geral no servidor de produção."
    },
    "output_parser": {
      "intencao": "Solicitacao",
      "urgencia": "Critica",
      "categoria_glpi": "Acessos",
      "confianca": 0.92,
      "resumo_demanda": "Solicitação crítica de privilégio de administrador geral em servidor de produção.",
      "resposta_sugerida": "Solicitação crítica de privilégio administrativo encaminhada obrigatoriamente para revisão e aprovação humana (Human-in-the-Loop), apesar da alta confiança na categorização.",
      "requer_revisao_humana": true
    },
    "decisao_gateway_n8n": "Revisao Humana"
  }
]
```

### 5.2 Exemplos Adicionais da Amostra Experimental (`N = 100`)
O conjunto completo com os 100 chamados sintéticos e seus respectivos gabaritos está publicado em:
- [`../data/chamados_sinteticos_100.json`](../data/chamados_sinteticos_100.json)
- [`../data/gabarito_classificacao_100.csv`](../data/gabarito_classificacao_100.csv)
