"""
02-AgentCore-Gateway/utils.py — helpers de AgentCore Gateway.

Funções:
    create_gateway_with_jwt_authorizer()    → cria gateway com Cognito JWT
    wait_for_gateway_ready()                → aguarda status READY
    add_lambda_target()                     → adiciona uma Lambda como MCP target
    add_all_lambda_targets()                → bulk add das 5 Lambdas com schemas
    get_mcp_endpoint()                      → URL completo do MCP endpoint
    cleanup_gateway()                       → remove gateway + targets
"""
from __future__ import annotations

import time
from typing import Any

import boto3
from botocore.exceptions import ClientError


# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas — descreve as Lambdas como MCP tools no Gateway
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS = {
    "gridapi": [
        {
            "name": "get_grid_status",
            "description": "Retorna status em tempo real da rede elétrica. Filtre por setor (norte/sul/leste/oeste).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Setor: norte, sul, leste, oeste. Omita para todos."}
                },
            },
        },
        {
            "name": "get_outage_alerts",
            "description": "Retorna alertas de blackouts. Filtre por severity (low/high) e status (active/resolved/all).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
    ],
    "maintenanceapi": [
        {
            "name": "create_work_order",
            "description": "Cria nova ordem de serviço. Status inicial: pending_approval.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "description": {"type": "string"},
                    "type": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["asset_id", "description"],
            },
        },
        {
            "name": "approve_work_order",
            "description": "Aprova OS pendente. Restrita a managers (Cedar P2). Identidade do aprovador vem do JWT.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["work_order_id"],
            },
        },
        {
            "name": "get_asset_history",
            "description": "Retorna histórico de manutenção de um ativo.",
            "inputSchema": {
                "type": "object",
                "properties": {"asset_id": {"type": "string"}},
                "required": ["asset_id"],
            },
        },
    ],
    "contractapi": [
        {
            "name": "search_contracts",
            "description": "Busca contratos com fornecedores. Filtre por category, status ou nome do supplier.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "status": {"type": "string"},
                    "supplier": {"type": "string"},
                },
            },
        },
        {
            "name": "extract_clause",
            "description": "Extrai cláusula específica (penalty, sla, termination, confidentiality).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contract_id": {"type": "string"},
                    "clause_type": {"type": "string"},
                },
                "required": ["contract_id", "clause_type"],
            },
        },
    ],
    "billingapi": [
        {
            "name": "get_invoice",
            "description": "Retorna fatura (contém PII). Restrito por Cedar P4.",
            "inputSchema": {
                "type": "object",
                "properties": {"invoice_id": {"type": "string"}},
                "required": ["invoice_id"],
            },
        },
        {
            "name": "get_consumption_history",
            "description": "Histórico de consumo do cliente B2B. Restrito por Cedar P4.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "months": {"type": "integer"},
                },
                "required": ["customer_id"],
            },
        },
    ],
    "regulatoryapi": [
        {
            "name": "generate_report",
            "description": "Gera relatório ANEEL. Tipos: DEC_FEC, VOLTAGE_QUALITY, FULL_COMPLIANCE.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "report_type": {"type": "string"},
                    "period": {"type": "string"},
                },
                "required": ["report_type", "period"],
            },
        },
        {
            "name": "submit_to_regulator",
            "description": "Submete relatório à ANEEL. BLOQUEADO por Cedar P6 (four-eyes).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "report_id": {"type": "string"},
                    "submitted_by": {"type": "string"},
                },
                "required": ["report_id", "submitted_by"],
            },
        },
        {
            "name": "get_compliance_data",
            "description": "Métricas DEC, FEC, VOLTAGE.",
            "inputSchema": {
                "type": "object",
                "properties": {"metric": {"type": "string"}},
            },
        },
    ],
}

# Mapeamento target name (sem _) → diretório Lambda (com _)
TARGET_TO_LAMBDA = {
    "gridapi": "grid_api",
    "maintenanceapi": "maintenance_api",
    "contractapi": "contract_api",
    "billingapi": "billing_api",
    "regulatoryapi": "regulatory_api",
}


# ─────────────────────────────────────────────────────────────────────────────
# Gateway
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_gateway(name: str, *, region: str = "us-east-1") -> dict | None:
    """Retorna o detail dict se um gateway com esse nome existir."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        resp = client.list_gateways()
        for gw in resp.get("items", []):
            if gw.get("name") == name:
                return client.get_gateway(gatewayIdentifier=gw["gatewayId"])
    except ClientError:
        pass
    return None


def create_gateway_with_jwt_authorizer(
    name: str,
    role_arn: str,
    *,
    discovery_url: str,
    allowed_clients: list[str] | None = None,
    allowed_scopes: list[str] | None = None,
    custom_claims: list[dict] | None = None,
    region: str = "us-east-1",
) -> dict:
    """
    Cria um Gateway com authorizer JWT do Cognito. Idempotente.

    Args:
        name: Nome do Gateway.
        role_arn: ARN da gateway role (use create_gateway_role do shared/utils/iam.py).
        discovery_url: URL do OpenID Connect (ex: cognito-idp.us-east-1.amazonaws.com/<pool>/.well-known/openid-configuration).
        allowed_clients: Lista de client_ids permitidos. Default: aceita qualquer.
        allowed_scopes: Lista de scopes permitidos. Default: ["aws.cognito.signin.user.admin"].
        custom_claims: Validações extras de claims. Default: token_use=access (recomendado).
        region: Região AWS.

    Returns:
        Dict com gateway_id, gateway_url, gateway_arn.
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    allowed_scopes = allowed_scopes or ["aws.cognito.signin.user.admin"]

    # Default custom claim: garante que é access token (não id token)
    if custom_claims is None:
        custom_claims = [{
            "inboundTokenClaimName": "token_use",
            "inboundTokenClaimValueType": "STRING",
            "authorizingClaimMatchValue": {
                "claimMatchValue": {"matchValueString": "access"},
                "claimMatchOperator": "EQUALS",
            },
        }]

    existing = find_existing_gateway(name, region=region)
    if existing:
        print(f"  ~ Gateway já existe: {existing['gatewayId']}")
        return {
            "gateway_id": existing["gatewayId"],
            "gateway_url": existing.get("gatewayUrl", ""),
            "gateway_arn": existing.get("gatewayArn", ""),
        }

    authorizer = {
        "discoveryUrl": discovery_url,
        "allowedScopes": allowed_scopes,
        "customClaims": custom_claims,
    }
    if allowed_clients:
        authorizer["allowedClients"] = allowed_clients

    resp = client.create_gateway(
        name=name,
        description="Workshop AI Agents Security — Gateway",
        roleArn=role_arn,
        protocolType="MCP",
        protocolConfiguration={"mcp": {"searchType": "SEMANTIC"}},
        authorizerType="CUSTOM_JWT",
        authorizerConfiguration={"customJWTAuthorizer": authorizer},
        tags={"project": "workshop-ai-agents-security"},
    )
    print(f"  ✓ Gateway criado: {resp['gatewayId']}")
    return {
        "gateway_id": resp["gatewayId"],
        "gateway_url": resp.get("gatewayUrl", ""),
        "gateway_arn": resp.get("gatewayArn", ""),
    }


def wait_for_gateway_ready(gateway_id: str, *, region: str = "us-east-1", timeout: int = 180) -> str:
    """Aguarda o Gateway atingir status READY. Retorna status final."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    elapsed = 0
    while elapsed < timeout:
        resp = client.get_gateway(gatewayIdentifier=gateway_id)
        status = resp.get("status")
        print(f"  Gateway status: {status} ({elapsed}s)")
        if status == "READY":
            return status
        if status in ("FAILED", "DELETED"):
            raise RuntimeError(f"Gateway atingiu estado terminal: {status}")
        time.sleep(5)
        elapsed += 5
    raise TimeoutError(f"Gateway não ficou READY em {timeout}s")


# ─────────────────────────────────────────────────────────────────────────────
# Lambda targets
# ─────────────────────────────────────────────────────────────────────────────

def add_lambda_target(
    gateway_id: str,
    target_name: str,
    lambda_arn: str,
    tool_schema: list[dict],
    *,
    region: str = "us-east-1",
) -> str:
    """
    Adiciona uma Lambda como target MCP no Gateway.

    Args:
        gateway_id: ID do gateway.
        target_name: Nome (sem underscores — Cognito API restriction).
        lambda_arn: ARN da Lambda (do Lab 02 ou shared.utils.lambda_helpers).
        tool_schema: Lista de tools com {name, description, inputSchema} — ver TOOL_SCHEMAS.
        region: Região AWS.

    Returns:
        target_id.
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        resp = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name,
            description=f"Lambda target: {target_name} ({len(tool_schema)} tool(s))",
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {"inlinePayload": tool_schema},
                    }
                }
            },
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
        target_id = resp["targetId"]
        print(f"  ✓ Target criado: {target_name} → {len(tool_schema)} tool(s)")
        return target_id
    except ClientError as e:
        if "ConflictException" in type(e).__name__ or "already exists" in str(e):
            existing = client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)
            for t in existing.get("items", []):
                if t.get("name") == target_name:
                    print(f"  ~ Target já existe: {target_name}")
                    return t["targetId"]
        raise


def add_all_lambda_targets(
    gateway_id: str,
    lambda_arns: dict[str, str],
    *,
    region: str = "us-east-1",
) -> dict[str, str]:
    """
    Adiciona todas as 5 Lambdas como targets, usando TOOL_SCHEMAS pré-definidos.

    Args:
        gateway_id: ID do gateway READY.
        lambda_arns: Dict {api_name: arn} — ex: {"grid_api": "arn:...", ...}.
        region: Região AWS.

    Returns:
        Dict {target_name: target_id}.
    """
    target_ids = {}
    for target_name, schema in TOOL_SCHEMAS.items():
        lambda_key = TARGET_TO_LAMBDA[target_name]
        lambda_arn = lambda_arns.get(lambda_key)
        if not lambda_arn:
            print(f"  ⚠ ARN ausente para {lambda_key}, pulando")
            continue
        target_ids[target_name] = add_lambda_target(
            gateway_id, target_name, lambda_arn, schema, region=region
        )
    return target_ids


def get_mcp_endpoint(gateway_url: str) -> str:
    """Constrói a URL completa do endpoint MCP a partir do gateway URL."""
    return gateway_url if gateway_url.endswith("/mcp") else f"{gateway_url.rstrip('/')}/mcp"


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_gateway(gateway_id: str, *, region: str = "us-east-1") -> bool:
    """Remove gateway e todos seus targets. Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        # Delete targets first
        targets = client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)
        for t in targets.get("items", []):
            client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=t["targetId"])
            print(f"  ✓ Target deletado: {t.get('name')}")
            time.sleep(2)
        client.delete_gateway(gatewayIdentifier=gateway_id)
        print(f"  ✓ Gateway deletado: {gateway_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            print(f"  ~ Gateway não existe (ok): {gateway_id}")
            return False
        raise


def cleanup_gateway_by_name(name: str, *, region: str = "us-east-1") -> bool:
    """Cleanup pelo nome (em vez de ID). Útil quando você não tem o ID em mãos."""
    existing = find_existing_gateway(name, region=region)
    if not existing:
        print(f"  ~ Gateway não existe (ok): {name}")
        return False
    return cleanup_gateway(existing["gatewayId"], region=region)
