# Dados mockados (seed data)

As 5 Lambda tools retornam dados fictícios determinísticos. Use os IDs
abaixo nos prompts do chat para que as respostas sejam realistas.

---

## GridAPI (`grid_api/lambda_function.py`)

### Setores conhecidos
`norte` · `sul` · `leste` · `oeste` · `centro`

### Exemplos de prompts
- "qual o status do setor norte?"
- "mostre a carga atual no setor centro"
- "há alertas críticos ativos?"
- "liste alertas de severidade alta"

### Formato de resposta
```json
{
  "sector": "norte",
  "status": "normal",
  "voltage_kv": 138.2,
  "load_mw": 245.7,
  "substations": 12,
  "active_alerts": 0,
  "timestamp": "2026-05-07T14:00:00Z"
}
```

---

## MaintenanceAPI (`maintenance_api/lambda_function.py`)

### Ordens pré-cadastradas
| ID | Ativo | Tipo | Status |
|---|---|---|---|
| WO-2024-0041 | SE-LESTE-03 | corrective | pending_approval |
| WO-2024-0038 | LT-NORTE-01 | preventive | approved |
| WO-2024-1021 | TR-042 | corrective | pending_approval |

### Ativos mencionáveis nos prompts
`TR-042` · `TR-003` · `SE-LESTE-03` · `LT-NORTE-01` · `TR-CENTRO-02`

### Exemplos de prompts
- "crie uma ordem de manutenção para o TR-042 com descrição 'troca de óleo', tipo preventiva, prioridade média"
- "aprove a ordem WO-1021" (❌ Ana: CEDAR BLOCKED P3 | ✅ Carlos: PERMIT P2)
- "mostre o histórico do ativo TR-042"

---

## ContractAPI (`contract_api/lambda_function.py`)

### Contratos pré-cadastrados
| ID | Fornecedor | Cláusulas disponíveis |
|---|---|---|
| CT-2023-0087 | Siemens Energy Brasil Ltda | SLA, penalidade, rescisão |
| CT-2024-0012 | Energisa Serviços S.A. | SLA, reajuste |
| CT-2022-0055 | ABB Ltda | manutenção preventiva, garantia |

### Exemplos de prompts
- "busque contratos de manutenção"
- "extraia a cláusula de SLA do contrato CT-2023-0087"
- "qual a penalidade do contrato com a Siemens?"

---

## BillingAPI (`billing_api/lambda_function.py`)

### Faturas pré-cadastradas
| ID | Cliente | Período |
|---|---|---|
| INV-2024-03-0091 | CLI-00234 | março/2024 |
| INV-2024-03-0092 | CLI-00891 | março/2024 |

### Clientes
`CLI-00234` · `CLI-00891`

### Exemplos de prompts
- "mostre a fatura INV-2024-03-0091" (❌ Ana: CEDAR BLOCKED P4 | ✅ Carlos: PERMIT)
- "qual o histórico de consumo do cliente CLI-00234, últimos 3 meses?"

> ℹ️ Respostas contêm **PII** (nome, CPF, endereço do cliente mockado) que
> o **Bedrock Guardrail** mascara automaticamente na saída — o cliente vê
> `{NOME}` e `{CPF}` em vez de dados reais.

---

## RegulatoryAPI (`regulatory_api/lambda_function.py`)

### Tipos de relatório
`Q1` · `Q2` · `Q3` · `Q4` · `annual` · `monthly`

### Reguladores
`ANEEL` · `ONS`

### Exemplos de prompts
- "gere o relatório Q1 de 2024 para a ANEEL" (❌ Ana: P5 | ✅ Carlos: PERMIT)
- "submeta o relatório RPT-2024-Q1 à ANEEL" (❌ **TODOS**: CEDAR BLOCKED P6 — four-eyes)
- "dados de compliance do Q1"

---

## Dica para o instrutor

Durante o workshop, copie estes IDs para o chat. Se um usuário iniciante
chutar um ID que não existe (ex: `TR-999`), o Lambda responde com erro
"not found" — que é interpretado como runtime error, não como Cedar deny
(badge mostra PERMIT + aparece mensagem amigável do agente pedindo um ID
válido).
