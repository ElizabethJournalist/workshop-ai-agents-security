# Lab 06 — Bedrock Guardrails


## O que você vai aprender

- Criar um [Bedrock Guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- Configurar masking de PII (CPF, EMAIL, ADDRESS, PASSWORD)
- Detecção de prompt injection (PROMPT_ATTACK)
- Wrapping defense in depth: input + output

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | — (Bedrock Guardrails, integrado ao Runtime) |
| Framework | — |
| Complexity | Easy |
| SDK | boto3 |

## Pré-requisitos

- ✅ [Lab 05 — Runtime](../05-AgentCore-Runtime/)

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-create-guardrail-and-wire-into-agents.ipynb` | PII + prompt injection |

## Outputs persistidos em `config.env`

```
BEDROCK_GUARDRAIL_ID, BEDROCK_GUARDRAIL_VERSION
```

## Next

➡️ [Lab 07 — Agent Registry](../07-Agent-Registry/)
