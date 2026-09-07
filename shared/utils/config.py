"""
shared.utils.config — Lê e escreve config.env entre os labs.

Cada notebook usa load_config() para ler o estado dos labs anteriores e
save_config(updates) para persistir suas saídas para os próximos.

Convenção:
    config.env vive na raiz do workshop (Workshop-AI-Agents-Security/).
    Linhas no formato KEY=VALUE, sem aspas, comentários começam com '#'.
    Linhas em branco ou vazias são preservadas em save_config().
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ENV = WORKSHOP_ROOT / "config.env"
CONFIG_ENV_EXAMPLE = WORKSHOP_ROOT / "config.env.example"


def _ensure_config_exists() -> None:
    """Cria config.env a partir do .example se ele não existir."""
    if CONFIG_ENV.exists():
        return
    if not CONFIG_ENV_EXAMPLE.exists():
        raise FileNotFoundError(
            f"Nem config.env nem config.env.example existem em {WORKSHOP_ROOT}"
        )
    CONFIG_ENV.write_text(CONFIG_ENV_EXAMPLE.read_text())
    print(f"  ℹ️  config.env criado a partir do .example")


def load_config(*, into_env: bool = True) -> dict[str, str]:
    """
    Lê config.env e retorna um dict com todas as variáveis.

    Args:
        into_env: Se True (default), também popula os.environ com as variáveis.
                  Útil para que helpers que usam os.environ as enxerguem.

    Returns:
        Dict {KEY: VALUE} com tudo do config.env (vazios incluídos).

    Exemplo:
        >>> cfg = load_config()
        >>> cfg["GATEWAY_ID"]
        'gateway-abc123'
        >>> os.environ["GATEWAY_ID"]   # populado automaticamente
        'gateway-abc123'
    """
    _ensure_config_exists()
    result: dict[str, str] = {}

    for line in CONFIG_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key] = value
        if into_env and value:
            os.environ[key] = value

    return result


def save_config(updates: dict[str, Any]) -> None:
    """
    Persiste alterações em config.env, preservando comentários e ordem.

    Para cada KEY em `updates`:
    - Se já existir no arquivo, atualiza o valor in-place.
    - Se não existir, adiciona no final.

    Valores são convertidos para string. Empty strings limpam o valor.

    Args:
        updates: Dict {KEY: value} com as alterações.

    Exemplo:
        >>> save_config({"GATEWAY_ID": "gw-abc", "GATEWAY_URL": "https://..."})
        ✓ config.env atualizado: GATEWAY_ID, GATEWAY_URL
    """
    _ensure_config_exists()
    if not updates:
        return

    # Stringify e popula os.environ logo
    str_updates = {k: str(v) if v is not None else "" for k, v in updates.items()}
    for k, v in str_updates.items():
        if v:
            os.environ[k] = v

    lines = CONFIG_ENV.read_text(encoding="utf-8").splitlines()
    keys_to_update = set(str_updates.keys())
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in keys_to_update:
            new_lines.append(f"{key}={str_updates[key]}")
            keys_to_update.discard(key)
        else:
            new_lines.append(line)

    # Append keys que não existiam ainda
    if keys_to_update:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key in sorted(keys_to_update):
            new_lines.append(f"{key}={str_updates[key]}")

    CONFIG_ENV.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    updated_keys = ", ".join(sorted(str_updates.keys()))
    print(f"  ✓ config.env atualizado: {updated_keys}")


def get_sector() -> str:
    """Atalho para obter o setor atual (env SECTOR ou config.env, default 'utility')."""
    if os.environ.get("SECTOR"):
        return os.environ["SECTOR"]
    cfg = load_config()
    return cfg.get("SECTOR") or "utility"


def get_region() -> str:
    """Atalho para obter a região AWS (env AWS_REGION ou config.env, default 'us-east-1')."""
    return os.environ.get("AWS_REGION") or load_config().get("AWS_REGION") or "us-east-1"


if __name__ == "__main__":
    import json
    cfg = load_config()
    populated = {k: v for k, v in cfg.items() if v}
    print(f"Setor: {get_sector()}")
    print(f"Região: {get_region()}")
    print(f"\n{len(populated)} variáveis preenchidas (de {len(cfg)} total):")
    print(json.dumps(populated, indent=2))
