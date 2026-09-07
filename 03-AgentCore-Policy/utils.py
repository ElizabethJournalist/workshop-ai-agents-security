"""
03-AgentCore-Policy/utils.py — helpers de Cedar Policy Engine.

Funções:
    create_policy_engine()                 → cria policy store
    add_policies_from_directory()          → carrega .cedar de shared/policies/<setor>/
    wait_policy_active()                   → aguarda status ACTIVE
    attach_engine_to_gateway()             → liga engine ao gateway
    set_policy_mode_enforce()              → ativa ENFORCE no gateway
    test_authorize_action()                → simula uma decisão Cedar
    cleanup_policy_engine()                → remove engine + policies
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


WORKSHOP_ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Policy templates — substitui placeholder {gateway_arn}
# ─────────────────────────────────────────────────────────────────────────────

def render_policy(cedar_template: str, gateway_arn: str) -> str:
    """
    Substitui o placeholder {gateway_arn} no template Cedar pelo ARN real.

    Os arquivos .cedar do workshop usam {gateway_arn} como placeholder.
    Quando carregamos do disco, fazemos format() — não usamos f-strings porque
    o cedar tem `{...}` em sintaxe (when blocks).
    """
    # Replace SOMENTE {gateway_arn} (não escape de outras chaves do cedar)
    return cedar_template.replace("{gateway_arn}", gateway_arn)


def load_policies_from_directory(
    sector: str,
    gateway_arn: str,
) -> list[tuple[str, str]]:
    """
    Carrega as policies .cedar do diretório do setor.

    Args:
        sector: 'utility', etc.
        gateway_arn: ARN do gateway (substitui {gateway_arn} se houver no template).

    Returns:
        Lista de (policy_name, cedar_text), ordenada por nome do arquivo.
    """
    policies_dir = WORKSHOP_ROOT / "shared" / "policies" / sector
    if not policies_dir.exists():
        raise FileNotFoundError(f"Diretório de policies não encontrado: {policies_dir}")

    result = []
    for cedar_file in sorted(policies_dir.glob("*.cedar")):
        name = cedar_file.stem  # ex: "P0AllAuthenticatedUsers"
        text = cedar_file.read_text(encoding="utf-8")
        text = render_policy(text, gateway_arn)
        result.append((name, text))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Policy engine
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_engine(name: str, *, region: str = "us-east-1") -> str | None:
    """Retorna engine_id se já existir."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        for key in ("items", "policyEngines"):
            engines = client.list_policy_engines().get(key, [])
            for e in engines:
                if e.get("name") == name:
                    return e.get("policyEngineId") or e.get("id")
    except ClientError:
        pass
    return None


def create_policy_engine(
    name: str = "workshop_policy_engine",
    *,
    description: str = "Workshop AI Agents Security — Cedar engine",
    region: str = "us-east-1",
) -> str:
    """Cria policy engine (ou retorna existente). Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    existing = find_existing_engine(name, region=region)
    if existing:
        print(f"  ~ Policy engine já existe: {existing}")
        return existing

    resp = client.create_policy_engine(name=name, description=description)
    engine_id = resp["policyEngineId"]
    print(f"  ✓ Policy engine criado: {engine_id}")
    # Aguarda ACTIVE (fiel à demo original setup_policies.py)
    for _ in range(30):
        r = client.get_policy_engine(policyEngineId=engine_id)
        if r.get("status") == "ACTIVE":
            break
        time.sleep(4)
    print(f"  ✓ Policy engine ACTIVE")
    return engine_id


def wait_policy_active(
    engine_id: str,
    policy_id: str,
    *,
    region: str = "us-east-1",
    timeout: int = 60,
) -> None:
    """Aguarda a policy atingir status ACTIVE."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get_policy(policyEngineId=engine_id, policyId=policy_id)
        if resp.get("status") == "ACTIVE":
            return
        time.sleep(4)
    raise TimeoutError(f"Policy {policy_id} não atingiu ACTIVE em {timeout}s")


def add_policy(
    engine_id: str,
    name: str,
    cedar_text: str,
    *,
    description: str = "",
    region: str = "us-east-1",
) -> tuple[str, bool]:
    """
    Adiciona uma policy ao engine. Idempotente — só atualiza se o conteúdo mudou.

    Returns:
        (policy_id, created) — created=True se a policy foi recém-criada.
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    desc = description or f"Workshop policy: {name}"

    # Lista policies existentes
    existing_id = None
    try:
        resp = client.list_policies(policyEngineId=engine_id, maxResults=100)
        for p in resp.get("policies", []):
            if p.get("name") == name:
                existing_id = p.get("policyId")
                break
    except ClientError:
        pass

    if existing_id:
        try:
            current = client.get_policy(policyEngineId=engine_id, policyId=existing_id)
            current_cedar = (
                (current.get("policy", {}).get("definition") or {})
                .get("cedar", {})
                .get("statement", "")
            )
            if current_cedar.strip() == cedar_text.strip():
                print(f"  ~ Policy existe (sem mudança): {name}")
                return existing_id, False
            client.update_policy(
                policyEngineId=engine_id,
                policyId=existing_id,
                description={"optionalValue": desc},
                definition={"cedar": {"statement": cedar_text}},
                validationMode="IGNORE_ALL_FINDINGS",
            )
            print(f"  ✓ Policy atualizada: {name}")
        except Exception as e:
            print(f"  ! Update falhou para {name}: {e}")
        return existing_id, False

    resp = client.create_policy(
        policyEngineId=engine_id,
        name=name,
        description=desc,
        definition={"cedar": {"statement": cedar_text}},
        validationMode="IGNORE_ALL_FINDINGS",
    )
    policy_id = resp["policyId"]
    print(f"  ✓ Policy criada: {name}")
    return policy_id, True


def add_all_policies(
    engine_id: str,
    sector: str,
    gateway_arn: str,
    *,
    region: str = "us-east-1",
) -> dict[str, str]:
    """Carrega e adiciona todas as policies do setor. Retorna {nome: policy_id}."""
    policies = load_policies_from_directory(sector, gateway_arn)
    if not policies:
        print(f"  ⚠ Nenhuma policy encontrada em shared/policies/{sector}/")
        return {}

    print(f"\nCarregando {len(policies)} policies do setor '{sector}':")
    result = {}
    created = []
    for name, cedar_text in policies:
        pid, was_created = add_policy(engine_id, name, cedar_text, region=region)
        result[name] = pid
        if was_created:
            created.append((name, pid))

    if created:
        print(f"  Aguardando {len(created)} policies ficarem ACTIVE...")
        for name, pid in created:
            wait_policy_active(engine_id, pid, region=region)
        print(f"  ✓ Todas ACTIVE")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Attach to gateway + ENFORCE mode
# ─────────────────────────────────────────────────────────────────────────────

def attach_engine_to_gateway(
    gateway_id: str,
    engine_id: str,
    *,
    region: str = "us-east-1",
    enforce: bool = True,
) -> None:
    """
    Liga o policy engine ao gateway via update_gateway.

    Também adiciona inline policy IAM na gateway role com permissões de
    AuthorizeAction/CheckAuthorizePermissions — necessário para o Gateway
    conseguir avaliar o Cedar engine (fiel à demo original setup_policies.py).

    Args:
        gateway_id: ID do gateway.
        engine_id: ID do policy engine.
        enforce: Se True (default), policy mode = ENFORCE.
                 Se False, fica em PERMIT (avalia mas não bloqueia).
    """
    import json as _json
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    engine_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:policy-engine/{engine_id}"
    mode = "ENFORCE" if enforce else "PERMIT"

    # 1. Adicionar permissões IAM na gateway role (AuthorizeAction + CheckAuthorizePermissions)
    gw_current = client.get_gateway(gatewayIdentifier=gateway_id)
    gw_role_arn = gw_current["roleArn"]
    role_name = gw_role_arn.split("/")[-1]
    iam = boto3.client("iam")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="AgentCorePolicyEnginePermissions",
        PolicyDocument=_json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ReadPolicyEngine",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetPolicyEngine",
                        "bedrock-agentcore:ListPolicies",
                        "bedrock-agentcore:GetPolicy",
                    ],
                    "Resource": engine_arn,
                },
                {
                    "Sid": "AuthorizeAgainstPolicyEngine",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:AuthorizeAction",
                        "bedrock-agentcore:PartiallyAuthorizeActions",
                        "bedrock-agentcore:CheckAuthorizePermissions",
                    ],
                    "Resource": "*",
                },
            ],
        }),
    )
    print(f"  ✓ IAM policy AgentCorePolicyEnginePermissions adicionada à role {role_name}")
    time.sleep(10)  # propagação IAM
    time.sleep(10)  # propagação IAM

    # 2. Re-envia todos os campos obrigatórios + atualiza policyEngineConfiguration
    update_kwargs = {
        "gatewayIdentifier": gateway_id,
        "name": gw_current["name"],
        "roleArn": gw_current["roleArn"],
        "protocolType": gw_current["protocolType"],
        "authorizerType": gw_current["authorizerType"],
        "authorizerConfiguration": gw_current.get("authorizerConfiguration", {}),
        "policyEngineConfiguration": {
            "arn": engine_arn,
            "mode": mode,
        },
    }
    if gw_current.get("description"):
        update_kwargs["description"] = gw_current["description"]
    if gw_current.get("protocolConfiguration"):
        update_kwargs["protocolConfiguration"] = gw_current["protocolConfiguration"]

    client.update_gateway(**update_kwargs)
    print(f"  ✓ Engine {engine_id} atrelado ao Gateway {gateway_id} (mode={mode})")


def set_policy_mode_enforce(gateway_id: str, *, region: str = "us-east-1") -> None:
    """Atalho para ativar ENFORCE em um gateway que já tem engine atrelado."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    current = client.get_gateway(gatewayIdentifier=gateway_id)
    pe = current.get("policyEngineConfiguration", {})
    if not pe.get("arn"):
        raise ValueError("Gateway não tem policy engine atrelado. Use attach_engine_to_gateway() antes.")

    update_kwargs = {
        "gatewayIdentifier": gateway_id,
        "name": current["name"],
        "roleArn": current["roleArn"],
        "protocolType": current["protocolType"],
        "authorizerType": current["authorizerType"],
        "authorizerConfiguration": current["authorizerConfiguration"],
        "policyEngineConfiguration": {"arn": pe["arn"], "mode": "ENFORCE"},
    }
    if current.get("description"):
        update_kwargs["description"] = current["description"]
    if current.get("protocolConfiguration"):
        update_kwargs["protocolConfiguration"] = current["protocolConfiguration"]

    client.update_gateway(**update_kwargs)
    print(f"  ✓ Gateway {gateway_id} agora em ENFORCE mode")


# ─────────────────────────────────────────────────────────────────────────────
# Test authorize via gateway real (não há API pública de simulação)
# ─────────────────────────────────────────────────────────────────────────────

async def _test_via_mcp_async(
    *,
    mcp_url: str,
    bearer_token: str,
    action: str,
    arguments: dict | None = None,
) -> dict:
    """Chama tool via MCP com bearer token. Retorna decisão observada."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {bearer_token}"}

    def _classify(msg: str) -> dict:
        lower = msg.lower()
        # AgentCore Cedar DENY messages
        if (
            "accessdenied" in lower
            or "tool execution denied" in lower
            or "policy evaluation denied" in lower
            or "policy enforcement" in lower
            or "denied due to" in lower
        ):
            # Tenta extrair o nome da policy responsável (ex: 'P3DenyOperatorApprove-xxx')
            import re
            m = re.search(r"\[Policy evaluation denied due to ([^\]]+)\]", msg)
            policy = m.group(1) if m else None
            return {"decision": "DENY", "policy": policy, "error": msg[:300]}
        return {"decision": "ERROR", "error": msg[:300]}

    try:
        async with streamablehttp_client(mcp_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name=action, arguments=arguments or {})
                return {
                    "decision": "ALLOW",
                    "result": result.content[0].text if result.content else "",
                }
    except BaseExceptionGroup as eg:
        # asyncio.TaskGroup wraps exceptions — desempacota
        all_msgs = []
        for exc in eg.exceptions:
            if isinstance(exc, BaseExceptionGroup):
                all_msgs.extend(str(e) for e in exc.exceptions)
            else:
                all_msgs.append(str(exc))
        return _classify(" | ".join(all_msgs))
    except Exception as e:
        return _classify(str(e))


def test_authorize_action(
    *,
    mcp_url: str,
    bearer_token: str,
    action: str,
    arguments: dict | None = None,
) -> dict:
    """
    Testa uma decisão Cedar fazendo a CHAMADA REAL via MCP no Gateway.

    Não existe API pública para simular decisões offline — então a única forma
    de validar é fazer a chamada e capturar PERMIT (sucesso) ou DENY
    (AccessDeniedException).

    Args:
        mcp_url: URL completo do MCP endpoint (cfg["GATEWAY_URL"]).
        bearer_token: JWT do usuário a testar (Ana ou Carlos).
        action: Nome da tool MCP (ex: 'gridapi___get_grid_status').
        arguments: Parâmetros da tool (para policies context-based como P8).

    Returns:
        Dict com:
          - decision: 'ALLOW' | 'DENY' | 'ERROR'
          - result (se ALLOW): texto da resposta da Lambda
          - error (se DENY/ERROR): primeira parte da mensagem
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # Em Jupyter já tem loop rodando
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(
            _test_via_mcp_async(
                mcp_url=mcp_url, bearer_token=bearer_token,
                action=action, arguments=arguments,
            )
        )
    except RuntimeError:
        # Sem loop rodando — script puro
        return asyncio.run(
            _test_via_mcp_async(
                mcp_url=mcp_url, bearer_token=bearer_token,
                action=action, arguments=arguments,
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_policy_engine(engine_id: str, *, region: str = "us-east-1") -> bool:
    """Remove engine + todas as policies. Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        # Delete policies first
        resp = client.list_policies(policyEngineId=engine_id, maxResults=100)
        for p in resp.get("items", []):
            client.delete_policy(policyEngineId=engine_id, policyId=p["policyId"])
            print(f"  ✓ Policy deletada: {p.get('name')}")
            time.sleep(1)
        client.delete_policy_engine(policyEngineId=engine_id)
        print(f"  ✓ Policy engine deletado: {engine_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            print(f"  ~ Engine não existe (ok): {engine_id}")
            return False
        raise
