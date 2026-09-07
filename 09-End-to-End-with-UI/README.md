# Lab 09 — End-to-End com UI


## O que você vai construir

Subir o portal Flask + Server-Sent Events que junta tudo dos labs 01-08
e executar visualmente as jornadas de Ana (operadora) e Carlos (gestor) —
demonstração visual da governança ponta a ponta.

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive + UI |
| AgentCore components | TODOS — Identity, Gateway, Policy, Memory, Runtime, Guardrails, Registry, Observability |
| Framework | Strands + Flask + SSE |
| Complexity | Medium |
| SDK | boto3 + Flask |

## Pré-requisitos

- ✅ Todos os labs 01–08 concluídos (idealmente — alguns podem ser pulados)

## O que tem aqui

```
09-End-to-End-with-UI/
├── README.md
├── ui/                      # Flask app + static (HTML/CSS/JS)
│   ├── server.py
│   └── static/
├── 01-launch-portal-and-run-journeys.ipynb
└── seed-data/               # symlinks para shared/seed-data/<setor>/
```

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-launch-portal-and-run-journeys.ipynb` | Sobe Flask, login Ana/Carlos, dispara jornadas |

## Outputs persistidos em `config.env`

```
PORTAL_HOST, PORTAL_PORT
```

## Next

🎉 Workshop concluído! Sugestões de próximos passos no notebook.
