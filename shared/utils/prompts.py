"""
shared.utils.prompts — Carrega prompts de SmartAgent por setor.

O SmartAgent (router) é o único agente UNIVERSAL — o mesmo arquivo .py
serve para qualquer setor. Apenas o prompt muda, lendo o arquivo
shared/prompts/<sector>/smart_agent.md em runtime.

Os specialists (agents/<sector>/*.py) NÃO usam este helper — seus prompts
ficam embutidos no próprio .py porque já são especializados por setor.
"""
from __future__ import annotations

import os
from pathlib import Path


# Raiz do workshop (sobe 2 níveis: shared/utils/ -> shared/ -> Workshop-AI-Agents-Security/)
WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = WORKSHOP_ROOT / "shared" / "prompts"


def load_smart_agent_prompt(sector: str | None = None) -> str:
    """
    Carrega o system prompt do SmartAgent para o setor solicitado.

    Args:
        sector: Nome do setor (ex: 'utility', 'healthcare', 'financial').
                Se None, usa a variável de ambiente SECTOR (default: 'utility').

    Returns:
        Conteúdo do arquivo shared/prompts/<sector>/smart_agent.md como string.

    Raises:
        FileNotFoundError: Se o arquivo do prompt não existir para o setor.

    Exemplo:
        >>> prompt = load_smart_agent_prompt()              # usa SECTOR de env
        >>> prompt = load_smart_agent_prompt("utility")     # explícito
    """
    sector = sector or os.environ.get("SECTOR", "utility")
    path = PROMPTS_DIR / sector / "smart_agent.md"

    if not path.exists():
        available = sorted(
            d.name for d in PROMPTS_DIR.iterdir()
            if d.is_dir() and (d / "smart_agent.md").exists()
        )
        raise FileNotFoundError(
            f"Prompt do SmartAgent não encontrado para setor '{sector}': {path}\n"
            f"Setores disponíveis: {available}\n"
            f"Crie shared/prompts/{sector}/smart_agent.md ou ajuste SECTOR."
        )

    return path.read_text(encoding="utf-8")


def list_available_sectors() -> list[str]:
    """Retorna a lista de setores que têm um smart_agent.md disponível."""
    if not PROMPTS_DIR.exists():
        return []
    return sorted(
        d.name for d in PROMPTS_DIR.iterdir()
        if d.is_dir() and (d / "smart_agent.md").exists()
    )


if __name__ == "__main__":
    import sys

    sectors = list_available_sectors()
    print(f"Setores com smart_agent.md disponível: {sectors}")

    sector = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"\nCarregando prompt para setor: {sector or os.environ.get('SECTOR', 'utility')}\n")
    print("─" * 60)
    print(load_smart_agent_prompt(sector))
