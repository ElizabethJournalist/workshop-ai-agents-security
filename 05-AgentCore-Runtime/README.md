# Lab 05 — AgentCore Runtime


## O que você vai aprender

- Deploy de agentes [Strands](https://strandsagents.com/) na AgentCore Runtime
- Pattern "Agents as Tools": SmartAgent (router) → 5 specialists
- Propagação de JWT do usuário em hops HTTPS
- Streaming via Server-Sent Events (SSE)

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Runtime, Gateway, Identity, Memory |
| Framework | Strands Agents |
| Models | Claude Haiku 4.5 (router) + Claude Sonnet 4.5 (specialists) |
| Complexity | Hard |
| SDK | boto3 + strands |

## Pré-requisitos

- ✅ [Lab 01 — Identity](../01-Identity-Foundation/)
- ✅ [Lab 02 — Gateway](../02-AgentCore-Gateway/)
- ✅ [Lab 04 — Memory](../04-AgentCore-Memory/)
- (recomendado) [Lab 03 — Policy](../03-AgentCore-Policy/)

## Estrutura de `agents/`

```
agents/
├── smart_agent.py            # ✨ universal — lê prompt de shared/prompts/<setor>/
└── <setor>/                  # specialists específicos do setor
    ├── base.py               # session manager + JWT helpers
    ├── grid_monitor_agent.py # specialists do utility...
    └── ... (5 no total para utility)
```

> 💡 O `smart_agent.py` é o mesmo arquivo independentemente do setor —
> apenas o prompt muda (carregado de `shared/prompts/<sector>/smart_agent.md`).
> Os specialists, ao contrário, têm o prompt embutido no `.py` porque já são
> especializados por setor.

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-deploy-router-agent.ipynb` | SmartAgent (Haiku) com prompt dinâmico |
| 2 | `02-deploy-specialists.ipynb` | 5 specialists (Sonnet) com MCP |
| 3 | `03-invoke-runtime-with-sse-streaming.ipynb` | SSE + JWT propagation |

## Outputs persistidos em `config.env`

```
RUNTIME_SMART_AGENT_ARN
RUNTIME_GRID_AGENT_ARN
RUNTIME_MAINTENANCE_AGENT_ARN
RUNTIME_CONTRACT_AGENT_ARN
RUNTIME_BILLING_AGENT_ARN
RUNTIME_REGULATORY_AGENT_ARN
RUNTIME_ROLE_ARN
```

## Next

➡️ [Lab 06 — Bedrock Guardrails](../06-Bedrock-Guardrails/)
