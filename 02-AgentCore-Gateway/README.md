# Lab 02 — AgentCore Gateway


## O que você vai aprender

- Criar um AgentCore Gateway com JWT inbound authorizer
- Adicionar Lambdas como targets (transformar APIs em MCP tools)
- Invocar tools via MCP client com bearer token

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Gateway, Identity (Cognito) |
| Framework | MCP client (streamable HTTP) |
| Complexity | Medium |
| SDK | boto3 + MCP |

## Pré-requisitos

- ✅ [Lab 01 — Identity](../01-Identity-Foundation/) concluído

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-create-gateway-with-jwt-authorizer.ipynb` | Gateway + customClaims + allowedScopes |
| 2 | `02-add-lambda-targets.ipynb` | 5 Lambdas → MCP tools |
| 3 | `03-invoke-mcp-with-bearer-token.ipynb` | Listar tools + chamar via MCP |

## Outputs persistidos em `config.env`

```
GATEWAY_ID, GATEWAY_ARN, GATEWAY_URL, GATEWAY_ROLE_ARN
LAMBDA_GRID_ARN, LAMBDA_MAINTENANCE_ARN, LAMBDA_CONTRACT_ARN,
LAMBDA_BILLING_ARN, LAMBDA_REGULATORY_ARN
```

## Next

➡️ [Lab 03 — AgentCore Policy](../03-AgentCore-Policy/)
