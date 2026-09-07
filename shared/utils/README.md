# shared/utils/ — infraestrutura cross-setor

Helpers utilitários que **não são AgentCore**. Ficam aqui para que o código
visível em cada lab (`.ipynb`) se concentre apenas no que é tema do lab.

```
shared/utils/
├── __init__.py
├── iam.py                # cria roles + policies (gateway, runtime, lambda)
├── lambda_helpers.py     # packaging (zip) + deploy de Lambdas
├── prompts.py            # load_smart_agent_prompt() — lê de shared/prompts/<setor>/
├── config.py             # load() / save() do config.env entre labs
└── cleanup.py            # delete_all() global por categoria (CLI)
```

## Princípio

| O que vai aqui | O que fica nos labs |
|---|---|
| 🛠️ Boilerplate AWS (IAM trust policies, Lambda zip, role creation) | 🎯 Código AgentCore (Gateway, Identity, Policy, Memory, Runtime, etc.) |
| Helpers de I/O (config.env, file paths) | Decisões de arquitetura (qual JWT, quais policies, qual model) |
| Cleanup global | Cleanup do recurso específico do lab |

Se um helper começa a falar de **AgentCore**, ele provavelmente deveria
estar no `utils.py` do lab específico, não aqui.

## Uso típico

```python
# Em qualquer notebook
from shared.utils.config import load_config, save_config
from shared.utils.iam import create_gateway_role
from shared.utils.lambda_helpers import deploy_lambda
from shared.utils.prompts import load_smart_agent_prompt

cfg = load_config()                                       # lê config.env
role_arn = create_gateway_role("workshop-gateway")        # 5+ linhas viram 1
save_config({"GATEWAY_ROLE_ARN": role_arn})               # persiste para próximo lab
```

## Cleanup

Cada lab tem sua seção de cleanup. Para um teardown completo:

```bash
python -m shared.utils.cleanup --all
# ou seletivo:
python -m shared.utils.cleanup --gateway --runtime
```

Será implementado no Chunk 2 (próximo).
