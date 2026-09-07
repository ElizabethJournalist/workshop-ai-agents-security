# Lab 07 — Agent Registry

## O que você vai aprender

- Criar um Agent Registry (catálogo de agentes)
- Registrar os 5 specialists como records `CUSTOM` com metadados de governança
  (risk_level, team, tools, policies, owasp_controls)
- Workflow de aprovação: **DRAFT → PENDING_APPROVAL → APPROVED → DEPRECATED**
- Discovery via `ListRegistryRecords` (descobrir agentes e seus metadados)

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Agent Registry |
| Framework | — |
| Complexity | Easy |
| SDK | boto3 |

## Pré-requisitos

- ✅ [Lab 05 — Runtime](../05-AgentCore-Runtime/) (precisa ter runtimes para registrar)

## Conceitos

- **Record (descriptor `CUSTOM`)**: cada agente vira um registro no catálogo com
  um documento JSON livre (`inlineContent`) descrevendo risco, time e controles.
- **Workflow de aprovação**: um record nasce em `DRAFT`; ao submeter
  (`SubmitRegistryRecordForApproval`) vai para `PENDING_APPROVAL`; a governança
  então marca como `APPROVED`. Agentes fora de uso vão para `DEPRECATED`.

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-create-registry-and-publish-agents.ipynb` | create_registry + register + submit + approve |
| 2 | `02-discover-and-status-lifecycle.ipynb` | discovery + lifecycle (DEPRECATED) |

## Outputs persistidos em `config.env`

```
AGENTCORE_REGISTRY_ID
```

## Next

➡️ [Lab 08 — AgentCore Observability](../08-AgentCore-Observability/)
