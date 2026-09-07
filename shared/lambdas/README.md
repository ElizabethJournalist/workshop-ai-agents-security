# Lambdas (por setor)

Código fonte das funções [AWS Lambda](https://docs.aws.amazon.com/lambda/) que
serão MCP-fied pelo Gateway no Lab 02.

```
shared/lambdas/
├── utility/                  # ⚡ setor energia — 5 APIs
│   ├── grid_api/             # rede elétrica
│   ├── maintenance_api/      # ordens de serviço
│   ├── contract_api/         # contratos
│   ├── billing_api/          # faturas
│   └── regulatory_api/       # ANEEL
├── healthcare/               # 🔜 placeholder
└── financial/                # 🔜 placeholder
```

> 💡 As Lambdas são **mocks** com dados fake hardcoded — o foco do workshop
> é a governança (Gateway + Cedar + Identity), não o backend de negócio.

## Estrutura de uma Lambda

```
shared/lambdas/<setor>/<api>/
├── lambda_function.py        # handler com mock data
├── requirements.txt          # opcional, se a Lambda tiver dependências
└── README.md                 # descreve as ações expostas
```

O handler segue o contrato do [Gateway Lambda target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-lambda.html):

```python
def lambda_handler(event, context):
    tool_name = context.client_context.custom["bedrockagentcoreToolName"]
    # ... routing per tool ...
    return {"statusCode": 200, "body": json.dumps(result)}
```

## Adicionar um novo setor

1. Crie `shared/lambdas/<novo_setor>/`
2. Adicione um sub-diretório por API (ex: `<novo_setor>/account_api/`)
3. Implemente `lambda_function.py` seguindo o contrato Gateway
4. Atualize as Cedar policies em `shared/policies/<novo_setor>/` (Lab 03)
5. Atualize seed data em `shared/seed-data/<novo_setor>/`
6. Defina `SECTOR=<novo_setor>` em `config.env` e re-execute o Lab 02

Os helpers em [`shared/utils/lambda_helpers.py`](../utils/lambda_helpers.py)
fazem o packaging (`zip`) e deploy de cada Lambda automaticamente,
percorrendo `shared/lambdas/<SECTOR>/`.
