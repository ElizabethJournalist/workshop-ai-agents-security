"""
shared.utils.cleanup — CLI de teardown global.

Uso:
    python -m shared.utils.cleanup --all
    python -m shared.utils.cleanup --lambdas --iam
    python -m shared.utils.cleanup --gateway --runtime --policy

Escopo coberto cresce conforme os labs vão sendo implementados. Cada lab
expõe sua própria função de cleanup local; este módulo orquestra todas.

Categorias suportadas (flags):
    --identity        Cognito User Pool (Lab 01)
    --gateway         Gateway + targets (Lab 02)
    --policy          Cedar Policy Store (Lab 03)
    --memory          Memory resource (Lab 04)
    --runtime         AgentCore Runtimes — 6 agentes (Lab 05)
    --guardrails      Bedrock Guardrail (Lab 06)
    --registry        Agent Registry (Lab 07)
    --observability   CloudTrail + alarms (Lab 08)
    --lambdas         5 Lambda mocks (parte do Lab 02)
    --iam             IAM roles criadas pelo workshop
    --all             Todas as categorias acima
    --dry-run         Mostra o que faria, sem deletar
"""
from __future__ import annotations

import argparse
import sys

from .config import get_region, get_sector, load_config
from .iam import delete_role
from .lambda_helpers import delete_all_for_sector


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup por categoria
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_lambdas(*, dry_run: bool = False) -> None:
    """Deleta as 5 Lambda mocks do setor atual."""
    sector = get_sector()
    region = get_region()
    print(f"\n[lambdas] sector={sector} region={region}")
    if dry_run:
        from .lambda_helpers import list_apis_for_sector
        for api in list_apis_for_sector(sector):
            print(f"  [DRY-RUN] deletaria: workshop-{sector}-{api}")
        return
    n = delete_all_for_sector(sector, region=region)
    print(f"  → {n} Lambda(s) removida(s)")


def cleanup_iam(*, dry_run: bool = False) -> None:
    """Deleta IAM roles criadas pelo workshop."""
    print("\n[iam] removing workshop roles")
    roles_to_delete = [
        "workshop-lambda-role",
        "workshop-gateway-role",
        # Runtime roles são por agente — adiciona conforme labs vão sendo deployados
        "workshop-runtime-smart-agent",
        "workshop-runtime-grid-monitor",
        "workshop-runtime-maintenance",
        "workshop-runtime-contract",
        "workshop-runtime-billing",
        "workshop-runtime-regulatory",
    ]
    if dry_run:
        for r in roles_to_delete:
            print(f"  [DRY-RUN] deletaria role: {r}")
        return
    for r in roles_to_delete:
        delete_role(r)


def cleanup_identity(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 3 (Lab 01)."""
    print("\n[identity] 🔜 será implementado quando o Lab 01 for criado (Chunk 3)")


def cleanup_gateway(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 4 (Lab 02)."""
    print("\n[gateway] 🔜 será implementado quando o Lab 02 for criado (Chunk 4)")


def cleanup_policy(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 5 (Lab 03)."""
    print("\n[policy] 🔜 será implementado quando o Lab 03 for criado (Chunk 5)")


def cleanup_memory(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 6 (Lab 04)."""
    print("\n[memory] 🔜 será implementado quando o Lab 04 for criado (Chunk 6)")


def cleanup_runtime(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 7 (Lab 05)."""
    print("\n[runtime] 🔜 será implementado quando o Lab 05 for criado (Chunk 7)")


def cleanup_guardrails(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 8 (Lab 06)."""
    print("\n[guardrails] 🔜 será implementado quando o Lab 06 for criado (Chunk 8)")


def cleanup_registry(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 9 (Lab 07)."""
    print("\n[registry] 🔜 será implementado quando o Lab 07 for criado (Chunk 9)")


def cleanup_observability(*, dry_run: bool = False) -> None:
    """🔜 Implementado no Chunk 10 (Lab 08)."""
    print("\n[observability] 🔜 será implementado quando o Lab 08 for criado (Chunk 10)")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = {
    "identity":      cleanup_identity,
    "gateway":       cleanup_gateway,
    "policy":        cleanup_policy,
    "memory":        cleanup_memory,
    "runtime":       cleanup_runtime,
    "guardrails":    cleanup_guardrails,
    "registry":      cleanup_registry,
    "observability": cleanup_observability,
    "lambdas":       cleanup_lambdas,
    "iam":           cleanup_iam,
}


# ORDEM importa: deletar dependentes antes de dependências (ex: gateway antes de lambdas).
# Roles do IAM ficam por último porque os recursos podem precisar delas durante delete.
ALL_ORDER = [
    "registry",
    "observability",
    "guardrails",
    "runtime",
    "memory",
    "policy",
    "gateway",
    "lambdas",
    "identity",
    "iam",
]


def main() -> int:
    p = argparse.ArgumentParser(
        prog="python -m shared.utils.cleanup",
        description="Teardown de recursos do Workshop-AI-Agents-Security",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python -m shared.utils.cleanup --all\n"
            "  python -m shared.utils.cleanup --lambdas --iam\n"
            "  python -m shared.utils.cleanup --gateway --dry-run\n"
        ),
    )
    for category in CATEGORIES:
        p.add_argument(f"--{category}", action="store_true", help=f"Limpar {category}")
    p.add_argument("--all", action="store_true", help="Limpar todas as categorias")
    p.add_argument("--dry-run", action="store_true", help="Mostrar sem deletar")
    args = p.parse_args()

    # Carrega config.env para que cleanups tenham acesso a IDs e ARNs
    load_config()

    selected = []
    if args.all:
        selected = ALL_ORDER
    else:
        for cat in ALL_ORDER:
            if getattr(args, cat, False):
                selected.append(cat)

    if not selected:
        p.print_help()
        print("\n⚠️  Nenhuma categoria selecionada. Use --all ou flags específicas.")
        return 1

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Cleanup das categorias:")
    print(f"  {', '.join(selected)}")
    print()

    for cat in selected:
        try:
            CATEGORIES[cat](dry_run=args.dry_run)
        except Exception as e:
            print(f"  ✗ Erro em {cat}: {e}")

    print("\n✓ Cleanup concluído.")
    if args.dry_run:
        print("  (dry-run — nada foi deletado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
