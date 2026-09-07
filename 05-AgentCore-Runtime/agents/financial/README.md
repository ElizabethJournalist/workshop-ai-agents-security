# agents/financial/

🔜 Setor placeholder.

Para ativar specialists no setor financeiro:

1. Crie os arquivos `.py` dos specialists (ex: `account_agent.py`,
   `credit_agent.py`, `kyc_agent.py`, `fraud_agent.py`)
2. Use [`agents/utility/base.py`](../utility/base.py) e os specialists
   como referência
3. Crie `shared/prompts/financial/smart_agent.md` listando esses specialists
4. Crie as Lambdas equivalentes em `shared/lambdas/financial/`
5. Crie as Cedar policies em `shared/policies/financial/`
   (segregação de funções, limites por valor, KYC, etc.)
6. Defina `SECTOR=financial` em `config.env`

> 💡 O `smart_agent.py` na raiz **não muda** — ele lê o prompt dinamicamente.
