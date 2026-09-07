# Lab 08 — AgentCore Observability


## O que você vai aprender

- Habilitar [AWS CloudTrail](https://docs.aws.amazon.com/cloudtrail/) multi-region para eventos AgentCore
- Consultar spans em `/aws/spans` (CloudWatch Logs)
- Configurar 8 alarmes para eventos críticos (DENY rate, latência, erros)
- Notificações via SNS (opcional)

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AgentCore components | Observability (atravessa todos os componentes) |
| Framework | — |
| Complexity | Medium |
| SDK | boto3 |

## Pré-requisitos

- Recomendado ter os labs 01–05 prontos para gerar eventos para inspecionar
- (Opcional) Lab 03 (Policy) ativo para gerar DENYs

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-cloudtrail-and-spans-aws-spans.ipynb` | CloudTrail + Logs Insights queries |
| 2 | `02-cloudwatch-alarms-for-governance.ipynb` | 8 alarmes + SNS |

## Outputs persistidos em `config.env`

```
CLOUDTRAIL_NAME, CLOUDTRAIL_BUCKET, SNS_ALARM_TOPIC_ARN
```

## Next

➡️ [Lab 09 — End-to-End com UI](../09-End-to-End-with-UI/)
