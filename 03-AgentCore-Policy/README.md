# Lab 03 — AgentCore Policy (Cedar)


## O que você vai aprender

- Linguagem [Cedar](https://www.cedarpolicy.com/) em 5 minutos
- Anexar policies a um Gateway e ativar `POLICY_MODE=ENFORCE`
- Testar PERMIT/DENY por persona (operadores vs gestores)
- Cedar avançado: control baseado em parâmetro (P8)

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Policy, Gateway |
| Framework | Cedar policy language |
| Complexity | Medium |
| SDK | boto3 |

## Pré-requisitos

- ✅ [Lab 01 — Identity](../01-Identity-Foundation/)
- ✅ [Lab 02 — Gateway](../02-AgentCore-Gateway/)

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-cedar-language-basics.ipynb` | P0–P3 com sintaxe explicada |
| 2 | `02-attach-policies-and-enforce.ipynb` | POLICY_MODE=ENFORCE no Gateway |
| 3 | `03-test-permit-deny-by-persona.ipynb` | Cenários Ana vs Carlos |
| 4 | `04-context-based-control-P8.ipynb` | Parameter-based (avançado) |

## Outputs persistidos em `config.env`

```
POLICY_STORE_ID, POLICY_MODE
```

## Next

➡️ [Lab 04 — AgentCore Memory](../04-AgentCore-Memory/)
