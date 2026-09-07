"""
tools/_nb.py — Helpers para construir notebooks Jupyter programaticamente.

Usage:
    from tools._nb import nb, md, code, save

    notebook = nb(
        md("# Lab 01 — ..."),
        md("## Setup"),
        code("import boto3"),
    )
    save(notebook, "01-Identity-Foundation/01-create-cognito-pool-with-groups.ipynb")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import nbformat
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
except ImportError as e:
    raise ImportError(
        "nbformat não está instalado. Rode: pip install nbformat"
    ) from e


def md(source: str) -> dict:
    """Cria uma cell de markdown."""
    return {"kind": "md", "source": source}


def code(source: str) -> dict:
    """Cria uma cell de código Python."""
    return {"kind": "code", "source": source}


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap — célula de upgrade de dependências (primeira de cada lab)
# ─────────────────────────────────────────────────────────────────────────────

BOOTSTRAP_MD = """## ⚙️ Setup do ambiente (rode na primeira vez)

A maioria dos serviços AgentCore (Gateway, Memory, Runtime, Registry) requer
versões recentes de `boto3`. Esta célula instala/atualiza tudo o que o
workshop precisa.

> ⚠️ **Após instalar, restart o kernel** (Kernel → Restart) e re-rode os
> notebooks. Você só precisa fazer isso **uma vez** por sessão do JupyterLab."""

BOOTSTRAP_CODE = """%pip install --quiet --upgrade \\
    boto3 botocore \\
    bedrock-agentcore bedrock-agentcore-starter-toolkit \\
    mcp PyJWT requests
print("✓ Dependências instaladas/atualizadas.")
print("⚠️  Se foi a primeira vez nesta sessão, restart o kernel agora")
print("   (Kernel → Restart Kernel) e re-rode os notebooks.")"""


def bootstrap_cells() -> list[dict]:
    """Retorna [markdown, code] para a seção de bootstrap do lab."""
    return [
        {"kind": "md", "source": BOOTSTRAP_MD},
        {"kind": "code", "source": BOOTSTRAP_CODE},
    ]


def nb(*cells: dict) -> Any:
    """
    Constrói um notebook a partir de cells.

    Args:
        *cells: Cells criadas com md() ou code().

    Returns:
        nbformat NotebookNode.
    """
    notebook = new_notebook()
    for c in cells:
        if c["kind"] == "md":
            notebook.cells.append(new_markdown_cell(c["source"]))
        elif c["kind"] == "code":
            notebook.cells.append(new_code_cell(c["source"]))
        else:
            raise ValueError(f"Kind desconhecido: {c['kind']}")
    notebook.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook.metadata.language_info = {"name": "python"}
    return notebook


def save(notebook: Any, path: str | Path) -> None:
    """Salva notebook em disco."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, path)
    print(f"  ✓ {path}")
