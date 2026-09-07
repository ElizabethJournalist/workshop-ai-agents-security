"""
shared.utils.lambda_helpers — Package & deploy das Lambdas por setor.

Convenção de pastas:
    shared/lambdas/<sector>/<api_name>/
    ├── lambda_function.py        ← handler obrigatório
    ├── requirements.txt          ← opcional (não usado neste workshop —
    │                              usamos boto3/json hardcoded)
    └── README.md                 ← documentação da API

Funções:
    package_lambda(sector, api_name)          → bytes de um zip pronto pro deploy
    deploy_lambda(api_name, role_arn, ...)    → idempotente: create ou update
    deploy_all_for_sector(sector, role_arn)   → bulk deploy de todas as APIs do setor
    delete_lambda(function_name)              → cleanup
"""
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
LAMBDAS_DIR = WORKSHOP_ROOT / "shared" / "lambdas"


# ─────────────────────────────────────────────────────────────────────────────
# Packaging
# ─────────────────────────────────────────────────────────────────────────────

def package_lambda(sector: str, api_name: str) -> bytes:
    """
    Empacota o código de uma Lambda em um zip in-memory pronto para deploy.

    Inclui todos os arquivos .py do diretório shared/lambdas/<sector>/<api_name>/.

    Args:
        sector: Ex: 'utility', 'healthcare'.
        api_name: Ex: 'grid_api', 'maintenance_api'.

    Returns:
        Bytes do zip, prontos para passar como Code={'ZipFile': bytes} no boto3.

    Raises:
        FileNotFoundError: Se o diretório ou lambda_function.py não existir.
    """
    src_dir = LAMBDAS_DIR / sector / api_name
    if not src_dir.exists():
        raise FileNotFoundError(f"Lambda source não encontrado: {src_dir}")

    handler = src_dir / "lambda_function.py"
    if not handler.exists():
        raise FileNotFoundError(
            f"Lambda handler não encontrado: {handler}\n"
            f"Toda Lambda do workshop precisa de lambda_function.py com lambda_handler()."
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for py_file in src_dir.rglob("*.py"):
            arcname = py_file.relative_to(src_dir).as_posix()
            zf.write(py_file, arcname)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Deploy (create or update)
# ─────────────────────────────────────────────────────────────────────────────

def deploy_lambda(
    api_name: str,
    role_arn: str,
    *,
    sector: str = "utility",
    function_name: str | None = None,
    region: str = "us-east-1",
    runtime: str = "python3.12",
    timeout: int = 30,
    memory_size: int = 128,
) -> str:
    """
    Faz deploy idempotente de uma Lambda — cria ou atualiza.

    Args:
        api_name: Nome do diretório em shared/lambdas/<sector>/.
        role_arn: ARN da execution role (use create_lambda_role() do iam.py).
        sector: Setor do qual extrair o código. Default: 'utility'.
        function_name: Nome final na AWS. Default: 'workshop-<sector>-<api_name>'.
        region: Região AWS. Default: 'us-east-1'.
        runtime: Runtime Lambda. Default: 'python3.12'.
        timeout: Timeout em segundos. Default: 30.
        memory_size: Memória em MB. Default: 128.

    Returns:
        ARN da função.
    """
    function_name = function_name or f"workshop-{sector}-{api_name}"
    client = boto3.client("lambda", region_name=region)
    zip_bytes = package_lambda(sector, api_name)

    try:
        client.get_function(FunctionName=function_name)
        # já existe — só atualiza o código
        resp = client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_bytes,
        )
        # aguarda o code update terminar antes de retornar
        waiter = client.get_waiter("function_updated")
        waiter.wait(FunctionName=function_name)
        print(f"  ✓ Lambda atualizada: {function_name}")
        return resp["FunctionArn"]
    except client.exceptions.ResourceNotFoundException:
        pass

    resp = client.create_function(
        FunctionName=function_name,
        Runtime=runtime,
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_bytes},
        Timeout=timeout,
        MemorySize=memory_size,
        Tags={
            "project": "workshop-ai-agents-security",
            "sector": sector,
            "api": api_name,
        },
    )
    waiter = client.get_waiter("function_active")
    waiter.wait(FunctionName=function_name)
    print(f"  ✓ Lambda criada: {function_name}")
    return resp["FunctionArn"]


def list_apis_for_sector(sector: str) -> list[str]:
    """
    Lista os nomes dos diretórios <api>/ em shared/lambdas/<sector>/.

    Inclui apenas pastas que tenham lambda_function.py (ignora placeholders).
    """
    sector_dir = LAMBDAS_DIR / sector
    if not sector_dir.exists():
        return []
    return sorted(
        d.name
        for d in sector_dir.iterdir()
        if d.is_dir() and (d / "lambda_function.py").exists()
    )


def deploy_all_for_sector(
    sector: str,
    role_arn: str,
    *,
    region: str = "us-east-1",
) -> dict[str, str]:
    """
    Faz deploy de todas as Lambdas do setor.

    Args:
        sector: Ex: 'utility'.
        role_arn: ARN da execution role.
        region: Região AWS.

    Returns:
        Dict {api_name: function_arn}.
    """
    apis = list_apis_for_sector(sector)
    if not apis:
        print(f"  ⚠️  Nenhuma Lambda encontrada em shared/lambdas/{sector}/")
        return {}

    print(f"\nDeploy de {len(apis)} Lambda(s) do setor '{sector}':")
    arns: dict[str, str] = {}
    for api in apis:
        arns[api] = deploy_lambda(api, role_arn, sector=sector, region=region)
    return arns


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def delete_lambda(function_name: str, *, region: str = "us-east-1") -> bool:
    """Remove uma Lambda. Idempotente — não falha se já não existir."""
    client = boto3.client("lambda", region_name=region)
    try:
        client.delete_function(FunctionName=function_name)
        print(f"  ✓ Lambda deletada: {function_name}")
        return True
    except client.exceptions.ResourceNotFoundException:
        print(f"  ~ Lambda não existe (ok): {function_name}")
        return False


def delete_all_for_sector(sector: str, *, region: str = "us-east-1") -> int:
    """Deleta todas as Lambdas do setor. Retorna quantas foram removidas."""
    apis = list_apis_for_sector(sector)
    count = 0
    for api in apis:
        function_name = f"workshop-{sector}-{api}"
        if delete_lambda(function_name, region=region):
            count += 1
    return count


if __name__ == "__main__":
    import sys
    sector = sys.argv[1] if len(sys.argv) > 1 else "utility"
    apis = list_apis_for_sector(sector)
    print(f"APIs detectadas em shared/lambdas/{sector}/:")
    for api in apis:
        print(f"  - {api}")
