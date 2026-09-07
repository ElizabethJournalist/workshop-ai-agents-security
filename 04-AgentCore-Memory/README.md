# Lab 04 — AgentCore Memory


## O que você vai aprender

- Criar um Memory resource (STM + LTM)
- Diferença entre Short-Term Memory (sessão atual) e Long-Term Memory (multi-sessão)
- Busca semântica em LTM com semantic strategies
- Como o `AgentCoreMemorySessionManager` integra com Strands

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Memory |
| Framework | — (boto3 puro neste lab) |
| Complexity | Easy |
| SDK | boto3 |

## Pré-requisitos

- Nenhum (Memory é independente — pode rodar antes ou em paralelo a Gateway)

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-create-memory-resource.ipynb` | ARN, status, semantic strategies |
| 2 | `02-stm-vs-ltm-and-semantic-search.ipynb` | Eventos, branching, busca |

## Outputs persistidos em `config.env`

```
MEMORY_ID, MEMORY_ARN
```

## Next

➡️ [Lab 05 — AgentCore Runtime](../05-AgentCore-Runtime/)
