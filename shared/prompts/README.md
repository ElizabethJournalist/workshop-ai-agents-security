# SmartAgent prompts (por setor)

Este diretório contém **apenas o prompt do SmartAgent** (router) por setor.
O código do SmartAgent em si fica em
[`05-AgentCore-Runtime/agents/smart_agent.py`](../../05-AgentCore-Runtime/agents/smart_agent.py)
e é **universal** — o mesmo `.py` serve para qualquer setor.

> 💡 **Por que só o SmartAgent é dinâmico?**  
> Os specialists (`agents/<setor>/*.py`) já são especializados por setor —
> seus prompts ficam embutidos no próprio `.py`, junto da lógica.  
> O SmartAgent, ao contrário, é genérico. O mesmo código serve para
> qualquer domínio; muda só o prompt (que diz quais specialists existem).

## Como funciona

`shared/utils/prompts.py::load_smart_agent_prompt(sector)` lê o arquivo
`shared/prompts/<sector>/smart_agent.md` em runtime. Por default usa a
variável de ambiente `SECTOR` (definida em `config.env`).

```python
# 05-AgentCore-Runtime/agents/smart_agent.py
from utils.prompts import load_smart_agent_prompt

SYSTEM_PROMPT = load_smart_agent_prompt()  # lê SECTOR de env, default 'utility'
```

## Setores disponíveis

| Setor | Status | Specialists conhecidos no prompt |
|---|---|---|
| `utility/` | ✅ pronto | grid, maintenance, contract, billing, regulatory |
| `healthcare/` | 🔜 placeholder | — |
| `financial/` | 🔜 placeholder | — |

## Adicionar um novo setor

1. Crie `shared/prompts/<novo_setor>/smart_agent.md` (use o de `utility/` como base)
2. Liste as tools `invoke_<specialist>` no formato:
   ```
   - invoke_<specialist_name>   <descrição curta dos casos de uso>
   ```
3. Crie os specialists em [`05-AgentCore-Runtime/agents/<novo_setor>/`](../../05-AgentCore-Runtime/agents/)
4. Defina `SECTOR=<novo_setor>` em `config.env`
5. Re-execute o Lab 05 para fazer deploy do SmartAgent com o novo prompt

> ⚠️ **Importante.** A lista de tools no prompt deve **bater exatamente**
> com os agentes que você vai expor como tools `@tool invoke_<x>` em
> `smart_agent.py`. O código gera tools dinamicamente baseado em variáveis
> de ambiente `RUNTIME_<SPECIALIST>_ARN` definidas pelo deploy.
