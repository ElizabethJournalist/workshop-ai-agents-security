# Cedar Policies (por setor)

Políticas [Cedar](https://www.cedarpolicy.com/) que o Gateway aplica em cada
chamada de tool MCP. São avaliadas pelo Policy Engine antes de executar a
Lambda — DENY = Lambda não é invocada.

```
shared/policies/
├── utility/                  # ⚡ 9 policies do setor energia (P0–P8)
│   ├── P0AllAuthenticatedUsers.cedar
│   ├── P1GridOperators.cedar
│   ├── P2ManagerApprove.cedar
│   ├── P3DenyOperatorApprove.cedar
│   ├── P4BillingIsolation.cedar
│   ├── P5RegulatoryExecutive.cedar
│   ├── P6BlockSubmitRegulator.cedar
│   ├── P7SemanticSearch.cedar
│   └── P8HighPriorityNeedsManager.cedar
├── healthcare/               # 🔜 placeholder
└── financial/                # 🔜 placeholder
```

## Convenção de nomes

`P<N><Description>.cedar` — `P0`..`P9` para ordering, `Description` em
PascalCase descrevendo a policy.

## Estrutura de uma policy

```cedar
permit (
    principal in CognitoGroup::"operators",
    action == AgentCore::Action::"gridapi___list_blackouts",
    resource
);
```

Cada arquivo deve conter **uma** policy (regra do Cedar Policy Engine v0).

## Adicionar um novo setor

1. Crie `shared/policies/<novo_setor>/`
2. Adicione policies seguindo a convenção `P<N><Description>.cedar`
3. As actions devem bater com os tool names do Gateway
   (`<api>___<operation>` — ex: `accountapi___get_balance`)
4. Defina `SECTOR=<novo_setor>` em `config.env` e re-execute o Lab 03

O Lab 03 inclui um exercício de **escrever sua própria policy** —
recomendamos rodar o lab `utility/` antes de adaptar para outro setor.
