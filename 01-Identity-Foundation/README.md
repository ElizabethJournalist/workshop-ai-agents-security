# Lab 01 — Identity Foundation

> 🏗️ **Este lab é a fundação de identidade do workshop** — não é AgentCore
> Identity propriamente dito, mas configura o que o AgentCore Identity vai
> consumir nos labs seguintes.

## Por que esse lab existe

AgentCore Identity precisa de um **IdP externo** que emita JWTs (Cognito,
Okta, Entra ID, etc.). Aqui usamos [Amazon Cognito](https://docs.aws.amazon.com/cognito/)
como IdP — é gratuito até 50.000 MAUs e está disponível em todas as regiões
comerciais.

> 💡 **Onde AgentCore Identity entra de fato?**
> - **Lab 02 (Gateway)** — `customJWTAuthorizer` é AgentCore Identity *inbound auth*
> - **Lab 05 (Runtime)** — mesmo authorizer aplica no Runtime
> - **Workload Identity Directory** — criado implicitamente quando você cria runtimes

## O que você vai construir aqui

- Um Cognito User Pool com 3 grupos (`operators`, `managers`, `governance`)
- 2 usuários de teste (Ana operadora, Carlos gestor)
- App client OAuth com `USER_PASSWORD_AUTH`
- Resource server com scopes
- JWTs reais com claim `cognito:groups` (que Cedar vai usar no Lab 03)

## Tutorial Details

| Information | Details |
|---|---|
| Tutorial type | Interactive |
| AWS components | Amazon Cognito |
| AgentCore components | — (preparação para os próximos labs) |
| Framework | — |
| Complexity | Easy |
| SDK | boto3 |

## Notebooks

| # | Arquivo | Tema |
|---|---|---|
| 1 | `01-create-cognito-pool-with-groups.ipynb` | User pool, grupos, usuários |
| 2 | `02-customclaims-and-allowedscopes.ipynb` | App client + JWT structure + preview do Gateway authorizer config |

## Outputs persistidos em `config.env`

```
COGNITO_USER_POOL_ID
COGNITO_USER_POOL_ARN
COGNITO_DOMAIN
COGNITO_DISCOVERY_URL
COGNITO_CLIENT_ID
COGNITO_CLIENT_SECRET
COGNITO_RESOURCE_SERVER_ID
```

## Next

➡️ [Lab 02 — AgentCore Gateway](../02-AgentCore-Gateway/) — onde o Cognito
é consumido pelo `customJWTAuthorizer` (AgentCore Identity *inbound auth*).
