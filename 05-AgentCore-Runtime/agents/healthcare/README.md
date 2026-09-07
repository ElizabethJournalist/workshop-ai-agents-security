# agents/healthcare/

🔜 Setor placeholder.

Para ativar specialists no setor de saúde:

1. Crie os arquivos `.py` dos specialists (ex: `clinical_agent.py`,
   `pharmacy_agent.py`)
2. Use [`agents/utility/base.py`](../utility/base.py) e os specialists
   como referência
3. Crie `shared/prompts/healthcare/smart_agent.md` listando esses specialists
4. Crie as Lambdas equivalentes em `shared/lambdas/healthcare/`
5. Crie as Cedar policies em `shared/policies/healthcare/`
6. Defina `SECTOR=healthcare` em `config.env`

> 💡 O `smart_agent.py` na raiz **não muda** — ele lê o prompt dinamicamente.
