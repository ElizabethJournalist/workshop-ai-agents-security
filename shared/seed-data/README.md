# Seed Data (por setor)

Dados fake (mock) usados pelas Lambdas do setor. Carregados em runtime
pelas Lambdas — vivem **apenas em memória** (não há banco de dados real
no workshop, para manter a barreira de entrada baixa).

```
shared/seed-data/
├── utility/                  # ⚡ setor energia
│   ├── customers.json        # ~50 clientes fictícios
│   ├── work-orders.json      # ordens de serviço
│   ├── contracts.json        # contratos vigentes
│   ├── grid-events.json      # eventos da rede (blackouts, sobrecargas)
│   └── invoices.json         # faturas
├── healthcare/               # 🔜 placeholder
└── financial/                # 🔜 placeholder
```

> ⚠️ **Não use dados reais.** Esses arquivos são só para teste pedagógico.
> Em produção, conecte as Lambdas a bancos de dados reais (RDS, DynamoDB,
> etc.) — não é o escopo deste workshop.

## Adicionar um novo setor

1. Crie `shared/seed-data/<novo_setor>/`
2. Adicione JSONs com a estrutura que suas Lambdas esperam
3. As Lambdas em `shared/lambdas/<novo_setor>/` lêem desses JSONs no `cold start`

> 💡 As Lambdas no demo `utility/` mostram o pattern de carregamento —
> use como referência ao adaptar para outro setor.
