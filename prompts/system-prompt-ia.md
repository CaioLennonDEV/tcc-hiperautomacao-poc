# System Prompt e Análise de Valor-Limite (Boundary Value Analysis) - Triagem Cognitiva de Chamados (GLPI)

## 1. Papel e Instrução Diretiva (System Prompt)
Você é um classificador determinístico para triagem de chamados do GLPI integrado à esteira de hiperautomação. Responda ESTRITAMENTE em formato JSON com as chaves: `intencao`, `urgencia`, `categoria_glpi`, `confianca` (0.0 a 1.0), `resumo_demanda`, `resposta_sugerida` e `requer_revisao_humana` (booleano, `true` se `confianca < 0.85` ou alta ambiguidade/risco crítico).

## 2. Regras de Execução e Metodologia de Limiar ABC
1. Responda exclusivamente em JSON válido conforme o esquema, sem blocos Markdown externos ou texto adicional.
2. Não alucine configurações de infraestrutura ou dados técnicos ausentes no relato original.
3. Aplique a avaliação probabilística de fronteira (Análise de Valor-Limite / *Boundary Value Analysis*) sobre o limiar `0.85`, especificando que a verificação dos valores limítrofes (0,84 abaixo do limiar, 0,85 exatamente no limiar e 0,86 acima do limiar) ocorre mediante injeção controlada de payloads no nó condicional (IF) do n8n:
   - **Caso A (Acima do Limiar — `confianca > 0.85`):** Demandas padronizadas, claras e recorrentes de N1 -> `requer_revisao_humana: false` (Fluxo Autônomo).
   - **Caso B (No Limiar Exato — `confianca == 0.85`):** Demandas com descrição suficiente para classificação categorial segura no limite operacional -> `requer_revisao_humana: false` (Fluxo Autônomo).
   - **Caso C (Abaixo do Limiar — `confianca < 0.85`):** Relatos vagos, múltiplos sintomas conflitantes ou solicitações críticas de segurança (ex.: liberação de firewall/root) -> `requer_revisao_humana: true` (Desvio *Human-in-the-Loop*).

## 3. Esquema JSON de Saída (Structured Output Parser)
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

## 4. Amostra de Textos Anonimizados de Teste (Bateria Experimental N = 100)

### 4.1 Cenários Padronizados (80% da amostra — Exemplo Caso A: `confianca > 0.85`)
```json
[
  {
    "ticket_id": 2001,
    "user_email": "carlos.souza@empresa.com",
    "ticket_title": "Esqueci minha senha de rede",
    "ticket_description": "Digitei a senha incorreta 3 vezes e bloqueou no AD.",
    "expected_category": "Acessos",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2002,
    "user_email": "mariana.costa@empresa.com",
    "ticket_title": "Solicitação de acesso ao ERP",
    "ticket_description": "Novo colaborador do financeiro precisa de perfil de leitura.",
    "expected_category": "Acessos",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2003,
    "user_email": "joao.pereira@empresa.com",
    "ticket_title": "Monitor não liga",
    "ticket_description": "Cabo de energia testado na tomada, mas o LED não acende.",
    "expected_category": "Hardware",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2004,
    "user_email": "fernanda.lima@empresa.com",
    "ticket_title": "VPN desconectando",
    "ticket_description": "Erro de autenticação SSL ao conectar de home office.",
    "expected_category": "Redes",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2005,
    "user_email": "ricardo.alves@empresa.com",
    "ticket_title": "Instalação do pacote Office",
    "ticket_description": "Preciso do Excel e Word ativados na estação 14.",
    "expected_category": "Software",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2006,
    "user_email": "juliana.rocha@empresa.com",
    "ticket_title": "Impressora do 2º andar atolada",
    "ticket_description": "Apresentando erro de bandeja e não puxa papel.",
    "expected_category": "Hardware",
    "expected_routing": "Automatico"
  }
]
```

### 4.2 Cenários de Fronteira e Ambíguos/Críticos (20% da amostra — Casos B = 0.85 e C < 0.85)
```json
[
  {
    "ticket_id": 2081,
    "user_email": "lucas.martins@empresa.com",
    "ticket_title": "Oscilação intermitente no link secundário",
    "ticket_description": "Queda rápida de pacotes na filial durante backup noturno, já voltou ao normal mas requer verificação da rota.",
    "boundary_case": "Caso B (Fronteira exata = 0.85)",
    "expected_routing": "Automatico"
  },
  {
    "ticket_id": 2083,
    "user_email": "mariana.costa@empresa.com",
    "ticket_title": "Problema no sistema",
    "ticket_description": "Dá erro quando tento salvar, mas às vezes vai. Verificar.",
    "boundary_case": "Caso C (Abaixo do limiar < 0.85)",
    "expected_routing": "Revisao Humana"
  },
  {
    "ticket_id": 2086,
    "user_email": "ricardo.alves@empresa.com",
    "ticket_title": "Erro 0x80040115",
    "ticket_description": "Apareceu essa janela na tela e fechou tudo que eu estava fazendo.",
    "boundary_case": "Caso C (Abaixo do limiar < 0.85)",
    "expected_routing": "Revisao Humana"
  },
  {
    "ticket_id": 2090,
    "user_email": "ana.silva@empresa.com",
    "ticket_title": "Não funciona nada aqui",
    "ticket_description": "O sistema parou depois que mexeram ontem, não sei se é rede ou PC.",
    "boundary_case": "Caso C (Abaixo do limiar < 0.85)",
    "expected_routing": "Revisao Humana"
  }
]
```
