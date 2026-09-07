# Workshop AI Agents Security

Workshop hands-on de governança e segurança para agentes de IA construídos
sobre [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/),
seguindo o estilo dos [AWS AgentCore Samples](https://github.com/awslabs/agentcore-samples).

Cada lab é um Jupyter notebook focado em **uma capability** do AgentCore.
A infraestrutura "boilerplate" (IAM, Lambda, etc.) é abstraída em
`shared/utils/` para que o código visível em cada notebook fique
concentrado **no que é AgentCore**.

---

## 🎯 O que você vai construir

Uma stack completa de governança aplicada ao setor de **utility** (energia
elétrica), composta de:

- 1 router agent (SmartAgent) + 5 specialists especializados em rede,
  manutenção, contratos, faturamento e regulatório
- Autenticação via Cognito com 3 grupos (operators, managers, governance)
- Gateway MCP com 5 Lambda tools, autorização JWT e Cedar policies P0–P8
- Memória de curto e longo prazo (STM/LTM) com busca semântica
- Bedrock Guardrails para PII e prompt injection
- Registry para catalogar agentes (DRAFT → PENDING_APPROVAL → APPROVED → DEPRECATED)
- Observabilidade ponta a ponta (CloudTrail + CloudWatch + spans + alarmes)
- Portal de teste com Server-Sent Events para validação visual

> 💡 **Multi-setor.** A estrutura `shared/<asset>/<setor>/` permite
> reusar a mesma stack para outros domínios (saúde, financeiro, varejo).
> Adicione `healthcare/` ou `financial/` com Lambdas, policies, seed data
> e specialists próprios — os labs aceitam a variável `SECTOR` em
> `config.env`.

---

## 📋 Pré-requisitos

| Item | Versão / detalhe |
|---|---|
| AWS Account com [Bedrock](https://docs.aws.amazon.com/bedrock/) habilitado | qualquer região comercial; usaremos `us-west-2` |
| Modelo Claude Sonnet 4.5 (specialists) | habilitado por default ([out/2025](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-automatic-enablement-serverless-foundation-models/)) |
| Modelo Claude Haiku 4.5 (router) | habilitado por default |
| AWS CLI 2.x | configurado com credenciais (`aws configure`) |
| Python | 3.10 ou superior |
| Jupyter Notebook ou JupyterLab | qualquer versão recente |
| Permissão IAM | `AdministratorAccess` (cria roles, Lambdas, Cognito, AgentCore resources, Guardrails, CloudTrail) |

> ⚠️ **Anthropic First Time Use.** Na primeira invocação dos modelos
> Anthropic em uma conta nova, o console pede um formulário (FTU) — submeta
> uma vez e vale para a conta toda. Ver [docs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

### Setup inicial

```bash
# Clone o workshop
git clone <este-repo>
cd Workshop-AI-Agents-Security

# Crie um virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Registre o kernel Jupyter
python3 -m ipykernel install --user --name=workshop-venv --display-name="Python (workshop-venv)"

# Inicie o Jupyter
jupyter notebook
```

> ℹ️ Em cada notebook, confirme que o kernel selecionado é
> **Python (workshop-venv)** (menu Kernel → Change kernel).

---

## 🗺️ Roteiro dos labs

Cada lab assume o stack do anterior. Variáveis de saída ficam em
`config.env` (criado a partir de `config.env.example`). Helpers em
`shared/utils/config.py` cuidam da persistência.

| # | Lab | Tema | Notebooks | Dependências |
|---|---|---|---|---|
| **01** | [Identity Foundation](./01-Identity-Foundation/) | Cognito IdP setup (fundação) + JWT preview | 2 | — |
| **02** | [AgentCore Gateway](./02-AgentCore-Gateway/) | MCP-fy de Lambdas com auth | 3 | 01 |
| **03** | [AgentCore Policy](./03-AgentCore-Policy/) | Cedar P0–P8 (PERMIT/DENY) | 4 | 02 |
| **04** | [AgentCore Memory](./04-AgentCore-Memory/) | STM + LTM + semantic search | 2 | — |
| **05** | [AgentCore Runtime](./05-AgentCore-Runtime/) | Deploy de 6 agentes Strands | 3 | 01, 02, 04 (03 recomendado) |
| **06** | [Bedrock Guardrails](./06-Bedrock-Guardrails/) | PII + prompt injection | 1 | 05 |
| **07** | [Agent Registry](./07-Agent-Registry/) | Catalogar agentes (status lifecycle) | 2 | 05 |
| **08** | [AgentCore Observability](./08-AgentCore-Observability/) | CloudTrail + spans + alarmes | 2 | atravessa todos |
| **09** | [End-to-End com UI](./09-End-to-End-with-UI/) | Portal Flask + jornadas Ana/Carlos | 1 | 01–08 |

---

## 📁 Estrutura do workshop

```
Workshop-AI-Agents-Security/
├── shared/
│   ├── utils/                    # 🛠️ infra cross-setor (IAM, Lambda, config, cleanup, prompts)
│   ├── prompts/<setor>/          # ✨ APENAS prompt do SmartAgent (universal por setor)
│   ├── lambdas/<setor>/<api>/    # APIs Lambda mock por setor
│   ├── policies/<setor>/         # Cedar policies por setor
│   ├── seed-data/<setor>/        # JSONs com customers, work orders, etc.
│   └── images/                   # diagramas globais
│
├── 01-Identity-Foundation/        # cada lab tem README + utils.py + .ipynb(s)
├── 02-AgentCore-Gateway/
├── 03-AgentCore-Policy/
├── 04-AgentCore-Memory/
├── 05-AgentCore-Runtime/
│   └── agents/
│       ├── smart_agent.py        # ✨ universal — lê prompt dinâmico de shared/prompts/<setor>/
│       └── <setor>/              # 5 specialists por setor
├── 06-Bedrock-Guardrails/
├── 07-Agent-Registry/
├── 08-AgentCore-Observability/
└── 09-End-to-End-with-UI/
```

---

## 💸 Custos esperados

Estimativa para rodar o workshop completo uma vez (criar tudo + executar
algumas chamadas + apagar tudo) em `us-west-2`, dentro de 1 dia:

| Serviço | Custo aproximado |
|---|---|
| Bedrock (Haiku + Sonnet, ~50 invocações) | ~ US$ 1.00 |
| AgentCore Runtime (6 agentes hospedados) | ~ US$ 0.50 |
| AgentCore Gateway + Memory + Registry | ~ US$ 0.20 |
| AWS Lambda (5 functions, mock invocations) | < US$ 0.01 |
| Cognito User Pool (até 50.000 MAUs grátis) | US$ 0.00 |
| CloudWatch Logs + CloudTrail | < US$ 0.05 |
| **Total** | **~ US$ 2.00** |

> ⚠️ Limpe os recursos após cada lab usando o **Cleanup section** no fim de
> cada notebook, ou rode o teardown completo: `python -m shared.utils.cleanup --all`

---

## 🔗 Referências

- [Amazon Bedrock AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AWS Labs AgentCore Samples](https://github.com/awslabs/agentcore-samples) (referência de estilo)
- [Strands Agents](https://strandsagents.com/) (framework usado nos labs)
- [Cedar policy language](https://www.cedarpolicy.com/)

---

## 📜 Licença

MIT — adapte para o seu uso.
